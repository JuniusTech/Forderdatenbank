"""Förderprogramm-Webseite — yapılandırılmış bilgi çıkarımı (Katman 3b).

Öncelik: Ollama (ücretsiz/yerel) → Claude API (yedek).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "page_extract_de.txt"


@dataclass
class PageExtractResult:
    status: str
    reason: str
    application_deadline: date | None = None
    funding_period: str | None = None
    application_possible: bool | None = None
    evidence_quote: str | None = None
    confidence: str = "low"
    method: str = "ollama"


def ai_fallback_available() -> bool:
    """Yerel Ollama veya Claude API kullanılabilir mi?"""
    provider = os.getenv("LIVE_CHECK_AI_PROVIDER", "auto").lower()
    if provider == "claude":
        return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    return True


def _parse_json_block(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        text = brace.group(0)
    return json.loads(text)


def _parse_deadline(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _normalize_status(value: str | None) -> str:
    status = str(value or "unknown").lower()
    if status not in {"active", "closed", "laufend", "unknown"}:
        return "unknown"
    return status


def _result_from_data(data: dict, *, method: str) -> PageExtractResult:
    label = "Ollama" if method == "ollama" else "Claude"
    return PageExtractResult(
        status=_normalize_status(data.get("status")),
        reason=str(data.get("reason_de") or f"{label}-Analyse"),
        application_deadline=_parse_deadline(data.get("application_deadline")),
        funding_period=data.get("funding_period"),
        application_possible=data.get("application_possible"),
        evidence_quote=(data.get("evidence_quote") or "")[:220] or None,
        confidence=str(data.get("confidence") or "medium"),
        method=method,
    )


def _build_user_payload(
    *,
    page_text: str,
    program_title: str,
    page_url: str,
    reference: date | None,
    text_limit: int = 12000,
) -> tuple[str, dict]:
    from ai.site_profiles import build_ai_site_hints

    ref = (reference or date.today()).isoformat()
    system = PROMPT_PATH.read_text(encoding="utf-8")
    user_payload = {
        "reference_date": ref,
        "program_title": program_title,
        "page_url": page_url,
        "site_hints": build_ai_site_hints(page_url),
        "page_text": page_text[:text_limit],
    }
    return system, user_payload


def _apply_site_postprocess(
    result: PageExtractResult,
    *,
    page_text: str,
    program_title: str,
    page_url: str,
) -> PageExtractResult:
    """Ollama low/unknown sonrası site kurallarıyla güçlendirme."""
    from ai.site_profiles import (
        build_ai_site_hints,
        page_has_program_substance,
        title_mentioned_in_text,
        url_is_insufficient,
    )

    hints = build_ai_site_hints(page_url)
    insufficient = url_is_insufficient(page_url) or hints.get("root_insufficient")

    # Hijack / root yetersiz / wrong overview: asla active/closed'a yükseltme
    if insufficient and result.status in {"active", "laufend", "closed"}:
        return PageExtractResult(
            status="unknown",
            reason=f"{result.reason} [site: insufficient_url → unknown]",
            application_deadline=result.application_deadline,
            funding_period=result.funding_period,
            application_possible=result.application_possible,
            evidence_quote=result.evidence_quote,
            confidence="low",
            method=f"{result.method}+site",
        )

    # Program anlatılmış + kapanış yok + domain prefer_active → unknown/low düzelt
    if (
        result.status == "unknown"
        and not insufficient
        and hints.get("prefer_active_if_described")
        and page_has_program_substance(page_text)
        and title_mentioned_in_text(program_title, page_text)
    ):
        closed_markers = (
            "nicht mehr möglich",
            "keine antragstellung",
            "antragsstopp",
            "mittel ausgeschöpft",
            "eingestellt",
            "ausgelaufen",
        )
        low = page_text.lower()
        if not any(m in low for m in closed_markers):
            return PageExtractResult(
                status="active",
                reason=(
                    f"{result.reason} [site: {hints.get('domain')} "
                    "Programm beschrieben ohne Schließung → active]"
                ),
                application_deadline=result.application_deadline,
                funding_period=result.funding_period,
                application_possible=True,
                evidence_quote=result.evidence_quote or page_text[:180],
                confidence="medium",
                method=f"{result.method}+site",
            )

    return result


def extract_page_with_ollama(
    *,
    page_text: str,
    program_title: str,
    page_url: str,
    reference: date | None = None,
) -> PageExtractResult | None:
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SEC", "90"))
    text_limit = int(os.getenv("OLLAMA_PAGE_TEXT_LIMIT", "5000"))

    system, user_payload = _build_user_payload(
        page_text=page_text,
        program_title=program_title,
        page_url=page_url,
        reference=reference,
        text_limit=text_limit,
    )

    try:
        response = httpx.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False),
                    },
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_predict": 1024},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        data = _parse_json_block(content)
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("error", "")
        except Exception:
            pass
        logger.warning("Ollama %s failed (%s): %s", model, exc.response.status_code, detail or exc)
        return None
    except Exception as exc:
        logger.warning("Ollama page extract failed: %s", exc)
        return None

    result = _result_from_data(data, method="ollama")
    return _apply_site_postprocess(
        result,
        page_text=page_text,
        program_title=program_title,
        page_url=page_url,
    )


def extract_page_with_claude(
    *,
    page_text: str,
    program_title: str,
    page_url: str,
    reference: date | None = None,
) -> PageExtractResult | None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None

    import anthropic

    system, user_payload = _build_user_payload(
        page_text=page_text,
        program_title=program_title,
        page_url=page_url,
        reference=reference,
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=800,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                }
            ],
        )
        data = _parse_json_block(message.content[0].text)
    except Exception as exc:
        logger.debug("Claude page extract failed: %s", exc)
        return None

    result = _result_from_data(data, method="claude")
    return _apply_site_postprocess(
        result,
        page_text=page_text,
        program_title=program_title,
        page_url=page_url,
    )


def extract_page_with_ai(
    *,
    page_text: str,
    program_title: str,
    page_url: str,
    reference: date | None = None,
) -> PageExtractResult | None:
    """Ollama önce (ücretsiz), sonra Claude yedek."""
    provider = os.getenv("LIVE_CHECK_AI_PROVIDER", "auto").lower()

    if provider in {"auto", "ollama"}:
        result = extract_page_with_ollama(
            page_text=page_text,
            program_title=program_title,
            page_url=page_url,
            reference=reference,
        )
        if result:
            return result
        if provider == "ollama":
            return None

    if provider in {"auto", "claude"}:
        return extract_page_with_claude(
            page_text=page_text,
            program_title=program_title,
            page_url=page_url,
            reference=reference,
        )

    return None
