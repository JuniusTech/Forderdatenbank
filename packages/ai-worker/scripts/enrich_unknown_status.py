"""status=unknown programları canlı URL ile zenginleştir (toplu, limitli)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter

from sqlalchemy import select

from db.models import FundingProgram
from db.session import get_session, init_db
from ingest.live_status import check_live_url
from matcher.live_verify import needs_live_check

logger = logging.getLogger(__name__)


def enrich_unknown(
    *,
    limit: int = 50,
    delay_sec: float = 1.0,
    apply: bool = False,
    dry_run: bool = False,
) -> dict:
    init_db()
    stats: Counter[str] = Counter()
    checked = 0
    updates: list[dict] = []

    with get_session() as session:
        rows = list(
            session.scalars(
                select(FundingProgram)
                .where(FundingProgram.status == "unknown")
                .where(FundingProgram.application_url.is_not(None))
                .where(FundingProgram.application_url != "")
                .order_by(FundingProgram.title)
                .limit(limit)
            ).all()
        )

        for program in rows:
            url = (program.application_url or "").strip()
            if not url or not needs_live_check(program.status):
                stats["skipped"] += 1
                continue

            checked += 1
            live = check_live_url(url)
            stats[live.status] += 1
            entry = {
                "title": program.title[:80],
                "url": url,
                "was": program.status,
                "live": live.status,
                "reason": live.reason,
                "closure_date": live.closure_date.isoformat() if live.closure_date else None,
            }
            updates.append(entry)

            if apply and not dry_run and live.status in {"closed", "active", "laufend"}:
                program.status = live.status
                stats["db_updated"] += 1

            if delay_sec > 0:
                time.sleep(delay_sec)

        if apply and not dry_run:
            session.commit()

    return {
        "candidates": len(rows),
        "checked": checked,
        "distribution": dict(stats),
        "samples": updates[:10],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nur status=unknown Programme per Live-URL prüfen"
    )
    parser.add_argument("--limit", type=int, default=50, help="Max Programm (default 50)")
    parser.add_argument("--delay", type=float, default=1.0, help="Sekunden zwischen Requests")
    parser.add_argument("--apply", action="store_true", help="Live-Ergebnis in DB schreiben")
    parser.add_argument("--dry-run", action="store_true", help="Nur report, kein DB write")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    report = enrich_unknown(
        limit=args.limit,
        delay_sec=args.delay,
        apply=args.apply,
        dry_run=args.dry_run,
    )

    print("\n=== UNKNOWN LIVE ENRICHMENT ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
