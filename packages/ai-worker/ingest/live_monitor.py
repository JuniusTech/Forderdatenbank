"""Zamanlanmış canlı URL izleme — unknown öncelik + active/laufend re-check."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import case, select

from db.models import FundingProgram
from db.session import get_session, init_db
from ingest.live_status import check_live_url

logger = logging.getLogger(__name__)

RESOLVED_STATUSES = frozenset({"active", "closed", "laufend"})
MODE_STATUSES = {
    "unknown": ("unknown",),
    "active": ("active", "laufend"),
    "all": ("unknown", "active", "laufend"),
}


def _make_client(use_browser: bool):
    if not use_browser:
        return None, None
    from ingest.browser_client import PlaywrightClient

    client = PlaywrightClient()
    client.__enter__()
    return client, client


def _select_programs(session, *, mode: str, limit: int) -> list[FundingProgram]:
    statuses = MODE_STATUSES[mode]
    priority = case(
        (FundingProgram.status == "unknown", 0),
        (FundingProgram.status == "laufend", 1),
        else_=2,
    )
    return list(
        session.scalars(
            select(FundingProgram)
            .where(FundingProgram.status.in_(statuses))
            .where(FundingProgram.application_url.is_not(None))
            .where(FundingProgram.application_url != "")
            .order_by(priority, FundingProgram.title)
            .limit(limit)
        ).all()
    )


def _apply_result(program: FundingProgram, live, *, url: str) -> bool:
    changed = False
    if live.status in RESOLVED_STATUSES and live.status != program.status:
        program.status = live.status
        changed = True
    if live.canonical_url and live.canonical_url.rstrip("/") != url.rstrip("/"):
        program.application_url = live.canonical_url
        changed = True
    return changed


def run_live_monitor(
    *,
    mode: str = "unknown",
    limit: int = 50,
    delay_sec: float = 1.5,
    apply: bool = False,
    dry_run: bool = False,
    use_ai: bool = True,
    use_browser: bool = True,
    timeout: float = 30.0,
    checkpoint: int = 10,
    log_path: Path | None = None,
) -> dict:
    if mode not in MODE_STATUSES:
        raise ValueError(f"Geçersiz mode: {mode}")

    init_db()
    stats: Counter[str] = Counter()
    checked = 0
    results: list[dict] = []
    client, cleanup = _make_client(use_browser)
    run_started = datetime.now(timezone.utc).isoformat()

    try:
        with get_session() as session:
            rows = _select_programs(session, mode=mode, limit=limit)
            logger.info(
                "Live monitor: %d kayıt (mode=%s, browser=%s, ai=%s)",
                len(rows),
                mode,
                use_browser,
                use_ai,
            )

            for idx, program in enumerate(rows, start=1):
                url = (program.application_url or "").strip()
                if not url:
                    stats["skipped"] += 1
                    continue

                was = program.status
                checked += 1
                live = check_live_url(
                    url,
                    client=client,
                    timeout=timeout,
                    program_title=program.title,
                    use_ai_fallback=use_ai,
                )
                stats[live.status] += 1
                changed = live.status != was
                if changed:
                    stats["status_changed"] += 1

                entry = {
                    "title": program.title[:80],
                    "url": url,
                    "was": was,
                    "live": live.status,
                    "changed": changed,
                    "method": live.method,
                    "reason": live.reason,
                    "closure_date": live.closure_date.isoformat() if live.closure_date else None,
                    "funding_period": live.funding_period,
                    "evidence": live.evidence_quote,
                    "canonical_url": live.canonical_url,
                    "redirect_type": live.redirect_type,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                results.append(entry)

                if apply and not dry_run and _apply_result(program, live, url=url):
                    stats["db_updated"] += 1

                logger.info(
                    "[%d/%d] %s | %s → %s (%s)%s",
                    idx,
                    len(rows),
                    program.title[:45],
                    was,
                    live.status,
                    live.method,
                    " *" if changed else "",
                )

                if apply and not dry_run and checkpoint > 0 and checked % checkpoint == 0:
                    session.commit()
                    logger.info("  ↳ checkpoint commit (%d)", checked)

                if delay_sec > 0:
                    time.sleep(delay_sec)

            if apply and not dry_run:
                session.commit()
    finally:
        if cleanup is not None:
            cleanup.close()

    report = {
        "run_started": run_started,
        "mode": mode,
        "candidates": len(results),
        "checked": checked,
        "distribution": dict(stats),
        "still_unknown": [r for r in results if r["live"] == "unknown"],
        "changed": [r for r in results if r["changed"]],
        "samples": results[:10],
        "all": results,
    }

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, ensure_ascii=False) + "\n")

    return report
