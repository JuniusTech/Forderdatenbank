"""Tüm programların status alanını XML'den yeniden hesaplar + dağılım raporu."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from sqlalchemy import select, text

from db.models import FundingProgram
from db.session import get_session, init_db
from ingest.deadline_parser import scan_program_fields
from ingest.link_resolver import LinkResolver
from ingest.program_parser import iter_program_files, parse_program_file

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPORT_ROOT = _REPO_ROOT / "BMWI"

CANONICAL_TESTS = [
    {
        "label": "Effiziente GebäudePLUS",
        "match": lambda t: "effiziente gebäude" in t.lower() and "plus" in t.lower(),
        "expect_status": "closed",
    },
    {
        "label": "Palu Modul 4",
        "match": lambda t: "palu" in t.lower() and "modul 4" in t.lower(),
        "expect_status": "active",
        "expect_end": date(2027, 1, 29),
    },
]


def recompute_statuses(source_root: Path, *, dry_run: bool = False) -> dict:
    source_root = source_root.resolve()
    resolver = LinkResolver(source_root)
    files = iter_program_files(source_root)

    distribution: Counter[str] = Counter()
    canonical_results: list[dict] = []
    parsed_by_source: dict[str, tuple[str, object]] = {}

    for path in files:
        parsed = parse_program_file(path, resolver)
        parsed_by_source[parsed.source_id] = (parsed.title, parsed)
        distribution[parsed.status] += 1

        for spec in CANONICAL_TESTS:
            if spec["match"](parsed.title):
                canonical_results.append(
                    {
                        "label": spec["label"],
                        "title": parsed.title,
                        "status": parsed.status,
                        "expect_status": spec["expect_status"],
                        "ok": parsed.status == spec["expect_status"],
                    }
                )

    report = {
        "total": sum(distribution.values()),
        "distribution": dict(sorted(distribution.items())),
        "canonical_tests": canonical_results,
    }

    if dry_run:
        return report

    init_db()
    with get_session() as session:
        rows = session.scalars(select(FundingProgram)).all()
        updated = 0
        for row in rows:
            entry = parsed_by_source.get(row.source_id)
            if not entry:
                continue
            _, parsed = entry
            if row.status != parsed.status:
                row.status = parsed.status
                updated += 1
        session.commit()
        db_dist = session.execute(
            text("SELECT status, COUNT(*) FROM funding_programs GROUP BY status ORDER BY status")
        ).all()
        report["db_updated"] = updated
        report["db_distribution"] = {status: count for status, count in db_dist}

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Program status yeniden hesapla")
    parser.add_argument("--source", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--dry-run", action="store_true", help="DB yazmadan dağılım raporu")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    report = recompute_statuses(args.source, dry_run=args.dry_run)

    print("\n=== STATUS DAĞILIMI ===")
    print(json.dumps(report["distribution"], indent=2, ensure_ascii=False))
    print(f"\nToplam: {report['total']}")

    print("\n=== KANONİK TESTLER ===")
    for t in report["canonical_tests"]:
        mark = "OK" if t["ok"] else "FAIL"
        print(f"  [{mark}] {t['label']}: {t['status']} (beklenen: {t['expect_status']})")
        print(f"         {t['title'][:70]}")

    if not args.dry_run and "db_distribution" in report:
        print(f"\nDB güncellenen: {report['db_updated']}")
        print("DB dağılım:", json.dumps(report["db_distribution"], ensure_ascii=False))

    failed = [t for t in report["canonical_tests"] if not t["ok"]]
    closed_ratio = report["distribution"].get("closed", 0) / max(report["total"], 1)
    if closed_ratio > 0.6:
        logger.warning("UYARI: closed oranı çok yüksek (%.0f%%) — parser agresif olabilir", closed_ratio * 100)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
