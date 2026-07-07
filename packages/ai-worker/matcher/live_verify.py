"""Eşleşme anında canlı URL doğrulama — Katman 3 (hedefli, cache'li)."""

from __future__ import annotations

import os
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests

from ingest.http_client import HttpClient
from ingest.live_status import LiveStatusResult, check_live_url
from matcher.pipeline import MatchResult
from ai.page_extractor import ai_fallback_available

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

CACHE_TTL_SEC = 4 * 3600  # 4 saat
DEFAULT_TIMEOUT = 12.0

_cache: dict[str, tuple[float, LiveStatusResult]] = {}
_shared_client: HttpClient | None = None


def _client() -> HttpClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = HttpClient()
    return _shared_client


def clear_live_cache() -> None:
    _cache.clear()


@dataclass
class LiveVerifyOutcome:
    result: MatchResult
    included: bool
    live_check: dict


def _cached_check(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    program_title: str = "",
    use_ai: bool | None = None,
) -> tuple[LiveStatusResult, bool]:
    now = time.time()
    hit = _cache.get(url)
    if hit and now - hit[0] < CACHE_TTL_SEC:
        return hit[1], True

    if use_ai is None:
        use_ai = ai_fallback_available()

    try:
        result = check_live_url(
            url,
            client=_client(),
            timeout=timeout,
            program_title=program_title,
            use_ai_fallback=use_ai,
        )
    except requests.RequestException as exc:
        result = LiveStatusResult(
            url=url,
            http_status=0,
            final_url=url,
            status="unknown",
            reason=f"Seite nicht erreichbar: {exc.__class__.__name__}",
        )
    _cache[url] = (now, result)
    return result, False


STATUSES_NEEDING_LIVE = frozenset({"unknown"})


def needs_live_check(program_status: str | None) -> bool:
    """Yalnızca XML deadline parser'ın karar veremediği programlar."""
    return (program_status or "unknown") in STATUSES_NEEDING_LIVE


def _skipped_live_check(program_status: str) -> dict:
    return {
        "ok": program_status != "closed",
        "status": program_status,
        "detail": f"XML-Status ({program_status}) — Live-Prüfung übersprungen",
        "snippet": None,
        "closure_date": None,
        "http_status": None,
        "cached": False,
        "skipped": True,
        "weight": 0,
    }


def live_check_to_dict(live: LiveStatusResult, *, cached: bool, skipped: bool = False) -> dict:
    return {
        "ok": live.status != "closed",
        "status": live.status,
        "detail": live.reason,
        "snippet": live.snippet,
        "closure_date": live.closure_date.isoformat() if live.closure_date else None,
        "http_status": live.http_status,
        "cached": cached,
        "skipped": skipped,
        "method": live.method,
        "funding_period": live.funding_period,
        "confidence": live.confidence,
        "evidence_quote": live.evidence_quote,
        "weight": 0,
    }


def verify_match_results(
    results: list[MatchResult],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    skip_without_url: bool = True,
) -> list[LiveVerifyOutcome]:
    """Top-N adayların application_url'lerini canlı doğrula; kapalıları ele."""
    outcomes: list[LiveVerifyOutcome] = []

    for match in results:
        url = (match.program.application_url or "").strip()
        xml_status = match.program.status or "unknown"

        if not needs_live_check(xml_status):
            breakdown = {
                **match.breakdown,
                "live_check": _skipped_live_check(xml_status),
            }
            outcomes.append(
                LiveVerifyOutcome(
                    result=MatchResult(
                        program=match.program,
                        score=match.score,
                        breakdown=breakdown,
                        matched_terms=match.matched_terms,
                        estimated_amount_range=match.estimated_amount_range,
                    ),
                    included=xml_status != "closed",
                    live_check=breakdown["live_check"],
                )
            )
            continue

        if not url:
            if skip_without_url:
                live = LiveStatusResult(
                    url="",
                    http_status=0,
                    final_url="",
                    status="unknown",
                    reason="Keine Antrags-URL hinterlegt",
                )
                breakdown = {**match.breakdown, "live_check": live_check_to_dict(live, cached=False)}
                outcomes.append(
                    LiveVerifyOutcome(
                        result=MatchResult(
                            program=match.program,
                            score=match.score,
                            breakdown=breakdown,
                            matched_terms=match.matched_terms,
                            estimated_amount_range=match.estimated_amount_range,
                        ),
                        included=True,
                        live_check=breakdown["live_check"],
                    )
                )
            continue

        live, cached = _cached_check(url, timeout=timeout, program_title=match.program.title)
        breakdown = {**match.breakdown, "live_check": live_check_to_dict(live, cached=cached)}
        included = live.status != "closed"
        if not included:
            logger.info("Live closed — ausgeschlossen: %s (%s)", match.program.title, url)

        outcomes.append(
            LiveVerifyOutcome(
                result=MatchResult(
                    program=match.program,
                    score=match.score,
                    breakdown=breakdown,
                    matched_terms=match.matched_terms,
                    estimated_amount_range=match.estimated_amount_range,
                ),
                included=included,
                live_check=breakdown["live_check"],
            )
        )

    return outcomes
