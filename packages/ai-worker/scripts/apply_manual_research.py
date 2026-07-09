"""Claude/manuel araştırma JSONL sonuçlarını funding_programs tablosuna uygula."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import or_, select

from db.models import FundingProgram
from db.session import get_session, init_db

logger = logging.getLogger(__name__)

APPLY_STATUSES = frozenset({"active", "closed", "laufend"})


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _find_program(session, row: dict) -> FundingProgram | None:
    url = (row.get("url") or "").strip()
    title = (row.get("title") or "").strip()
    if url:
        hit = session.scalar(
            select(FundingProgram).where(FundingProgram.application_url == url).limit(1)
        )
        if hit:
            return hit
    if title:
        return session.scalar(
            select(FundingProgram)
            .where(
                or_(
                    FundingProgram.title == title,
                    FundingProgram.title.ilike(f"{title[:60]}%"),
                )
            )
            .limit(1)
        )
    return None


def apply_manual_research(path: Path, *, dry_run: bool = False) -> dict:
    init_db()
    stats = {"rows": 0, "matched": 0, "updated": 0, "skipped": 0, "not_found": 0}
    details: list[dict] = []

    with path.open(encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]

    with get_session() as session:
        for line in lines:
            stats["rows"] += 1
            row = json.loads(line)
            status = (row.get("status") or "unknown").strip()
            program = _find_program(session, row)
            if program is None:
                stats["not_found"] += 1
                details.append({"title": row.get("title"), "result": "not_found"})
                continue

            stats["matched"] += 1
            if status not in APPLY_STATUSES:
                stats["skipped"] += 1
                details.append({"title": program.title[:60], "result": "skipped", "status": status})
                continue

            old_status = program.status
            program.status = status
            canonical = (row.get("canonical_url") or "").strip() or None
            if canonical and canonical.rstrip("/") != (program.application_url or "").rstrip("/"):
                program.application_url = canonical

            stats["updated"] += 1
            details.append(
                {
                    "title": program.title[:60],
                    "result": "updated",
                    "was": old_status,
                    "now": status,
                    "url": program.application_url,
                }
            )
            logger.info("%s: %s → %s", program.title[:50], old_status, status)

        if not dry_run:
            session.commit()

    return {"stats": stats, "details": details}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manuel JSONL araştırma sonuçlarını DB'ye yaz")
    parser.add_argument("jsonl", type=Path, help="manual_research_batchN.jsonl dosyası")
    parser.add_argument("--dry-run", action="store_true", help="DB yazma, sadece rapor")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    if not args.jsonl.exists():
        logger.error("Dosya bulunamadı: %s", args.jsonl)
        return 1

    report = apply_manual_research(args.jsonl, dry_run=args.dry_run)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
