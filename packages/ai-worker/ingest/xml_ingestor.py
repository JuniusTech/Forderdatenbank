"""XML ZIP snapshot ingestor — Faz 1b."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from db.models import FundingProgram, XmlIngestRun
from db.session import get_session, init_db
from ingest.link_resolver import LinkResolver
from ingest.program_parser import iter_program_files, parse_program_file

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPORT_ROOT = _REPO_ROOT / "BMWI"


def _default_source_root() -> Path:
    return DEFAULT_EXPORT_ROOT


def upsert_program(session, parsed, now: datetime) -> str:
    existing = session.scalar(
        select(FundingProgram).where(FundingProgram.source_id == parsed.source_id)
    )
    if existing is None:
        session.add(
            FundingProgram(
                **parsed.to_db_payload(),
                first_seen_at=now,
                last_synced_at=now,
            )
        )
        return "new"

    if existing.content_hash == parsed.content_hash:
        existing.last_synced_at = now
        return "skipped"

    payload = parsed.to_db_payload()
    for key, value in payload.items():
        setattr(existing, key, value)
    existing.last_synced_at = now
    return "updated"


def verify_ingest(source_root: Path, *, limit: int | None = None) -> dict[str, int | list[str]]:
    """Dosya sayısı ile DB kayıt sayısını karşılaştır; eksik source_id'leri listele."""
    from sqlalchemy import text

    source_root = source_root.resolve()
    files = iter_program_files(source_root)
    if limit is not None:
        files = files[:limit]

    expected_ids: set[str] = set()
    for path in files:
        from ingest.xml_utils import parse_xml

        root = parse_xml(path)
        name = root.get("name") or path.stem
        doc_path = root.get("path") or str(path.parent)
        expected_ids.add(f"{doc_path}/{name}")

    with get_session() as session:
        if limit is None:
            db_count = session.scalar(text("SELECT COUNT(*) FROM funding_programs"))
            rows = session.execute(text("SELECT source_id FROM funding_programs")).fetchall()
        else:
            placeholders = ", ".join(f":id{i}" for i in range(len(expected_ids)))
            if not expected_ids:
                return {"file_count": 0, "db_count": 0, "missing": []}
            params = {f"id{i}": sid for i, sid in enumerate(expected_ids)}
            db_count = session.scalar(
                text(f"SELECT COUNT(*) FROM funding_programs WHERE source_id IN ({placeholders})"),
                params,
            )
            rows = session.execute(
                text(f"SELECT source_id FROM funding_programs WHERE source_id IN ({placeholders})"),
                params,
            ).fetchall()

    actual_ids = {row[0] for row in rows}
    missing = sorted(expected_ids - actual_ids)
    return {
        "file_count": len(expected_ids),
        "db_count": db_count or 0,
        "missing": missing,
    }


def run_ingest(
    source_root: Path,
    *,
    limit: int | None = None,
    commit_every: int = 200,
    verify: bool = True,
) -> dict[str, int | str | list[str]]:
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Export kökü bulunamadı: {source_root}")

    init_db()
    resolver = LinkResolver(source_root)
    files = iter_program_files(source_root)
    if limit is not None:
        files = files[:limit]

    run = XmlIngestRun(source_root=str(source_root))
    now = datetime.now(timezone.utc)

    with get_session() as session:
        session.add(run)
        session.flush()

        for index, path in enumerate(files, start=1):
            try:
                parsed = parse_program_file(path, resolver)
                result = upsert_program(session, parsed, now)
                run.programs_processed += 1
                if result == "new":
                    run.new_count += 1
                elif result == "updated":
                    run.updated_count += 1
                else:
                    run.skipped_count += 1
            except Exception as exc:  # noqa: BLE001 — ingest run özeti için yakala
                run.error_count += 1
                run.errors = [
                    *run.errors,
                    {"file": str(path), "error": str(exc)},
                ]
                logger.exception("Parse hatası: %s", path)

            if index % commit_every == 0:
                session.commit()
                logger.info(
                    "İlerleme: %s/%s (yeni=%s güncellenen=%s atlanan=%s hata=%s)",
                    index,
                    len(files),
                    run.new_count,
                    run.updated_count,
                    run.skipped_count,
                    run.error_count,
                )

        run.finished_at = datetime.now(timezone.utc)
        session.add(run)
        summary = {
            "run_id": str(run.run_id),
            "programs_processed": run.programs_processed,
            "new_count": run.new_count,
            "updated_count": run.updated_count,
            "skipped_count": run.skipped_count,
            "error_count": run.error_count,
        }

    if verify:
        check = verify_ingest(source_root, limit=limit)
        summary["file_count"] = check["file_count"]
        summary["db_count"] = check["db_count"]
        summary["missing"] = check["missing"]
        if check["file_count"] != check["db_count"]:
            logger.error(
                "Doğrulama BAŞARISIZ: dosya=%s db=%s eksik=%s",
                check["file_count"],
                check["db_count"],
                len(check["missing"]),
            )
            for sid in check["missing"][:20]:
                logger.error("  eksik: %s", sid)
            if len(check["missing"]) > 20:
                logger.error("  ... ve %s eksik daha", len(check["missing"]) - 20)
        else:
            logger.info(
                "Doğrulama OK: dosya=%s db=%s",
                check["file_count"],
                check["db_count"],
            )

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Förderdatenbank XML ingestor")
    parser.add_argument(
        "--source",
        type=Path,
        default=_default_source_root(),
        help="BMWI export kök klasörü",
    )
    parser.add_argument("--limit", type=int, default=None, help="Test için max program sayısı")
    parser.add_argument(
        "--commit-every",
        type=int,
        default=200,
        help="Kaç kayıtta bir commit (kesilirse kaldığı yerden devam için)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Import sonrası dosya/DB sayısı doğrulamasını atla",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        summary = run_ingest(
            args.source,
            limit=args.limit,
            commit_every=args.commit_every,
            verify=not args.no_verify,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    print(
        f"Tamamlandı: işlenen={summary['programs_processed']} yeni={summary['new_count']} "
        f"güncellenen={summary['updated_count']} atlanan={summary['skipped_count']} "
        f"hata={summary['error_count']}"
    )
    if "file_count" in summary:
        print(f"Doğrulama: dosya={summary['file_count']} db={summary['db_count']}")
        if summary["file_count"] != summary["db_count"]:
            missing = summary.get("missing", [])
            print(f"BAŞARISIZ — {len(missing)} eksik kayıt")
            for sid in missing[:10]:
                print(f"  eksik: {sid}")
            return 3

    return 0 if summary["error_count"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
