"""Claude/manuel araştırma JSONL sonuçlarını funding_programs tablosuna uygula."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from sqlalchemy import select

from db.models import FundingProgram
from db.session import SessionLocal, init_db

logger = logging.getLogger(__name__)

APPLY_STATUSES = frozenset({"active", "closed", "laufend"})


def _title_score(program_title: str, query_title: str) -> int:
    """Aynı URL adayları arasında en iyi başlık eşleşmesi."""
    a = (program_title or "").lower().strip()
    b = (query_title or "").lower().strip()
    if not a or not b:
        return 0
    if a == b:
        return 1000
    # Daha spesifik DB başlığı (query prefix ise) tercih
    if a.startswith(b) or b.startswith(a):
        # Daha uzun eşleşme = daha spesifik (Energiekredit vs Energiekredit Gebäude)
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        if longer.startswith(shorter) and len(longer) - len(shorter) > 3:
            # exact shorter query should prefer exact shorter program
            if len(a) <= len(b):
                return 600 + len(a)
            return 400 + len(b)
        return 500 + min(len(a), len(b))
    words = [w for w in b.replace("/", " ").replace("–", " ").replace("?", " ").split() if len(w) > 4]
    if not words:
        return 0
    hits = sum(1 for w in words if w in a)
    if hits < 2:
        return 0
    return hits * 20 + (10 if abs(len(a) - len(b)) < 15 else 0)


def _find_program(session, row: dict) -> FundingProgram | None:
    url = (row.get("url") or "").strip()
    title = (row.get("title") or "").strip()
    if url:
        candidates = list(
            session.scalars(
                select(FundingProgram).where(FundingProgram.application_url == url)
            ).all()
        )
        # canonical_url ile de ara
        canonical = (row.get("canonical_url") or "").strip()
        if not candidates and canonical:
            candidates = list(
                session.scalars(
                    select(FundingProgram).where(FundingProgram.application_url == canonical)
                ).all()
            )
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1 and title:
            ranked = sorted(
                candidates,
                key=lambda p: _title_score(p.title, title),
                reverse=True,
            )
            if _title_score(ranked[0].title, title) > 0:
                return ranked[0]
            # Skor 0 → yanlış adayı seçme; title ile devam
            candidates = []
        elif candidates and not title:
            return candidates[0]
    if title:
        exact = session.scalar(
            select(FundingProgram).where(FundingProgram.title == title).limit(1)
        )
        if exact:
            return exact
        # ilike adayları: en kısa / en yakın başlık (Energiekredit ≠ Energiekredit Regenerativ)
        loose = list(
            session.scalars(
                select(FundingProgram)
                .where(FundingProgram.title.ilike(f"{title[:60]}%"))
                .limit(20)
            ).all()
        )
        if not loose:
            return None
        loose.sort(key=lambda p: (abs(len(p.title) - len(title)), len(p.title)))
        best = loose[0]
        if _title_score(best.title, title) > 0 or best.title.lower().startswith(title[:40].lower()):
            # Exact-prefix ama fazla uzun eklenti varsa reddet ( +3 kelime)
            if best.title.lower() != title.lower():
                extra = best.title[len(title) :].strip(" –-?")
                if extra and len(extra) > 3 and not title.lower().endswith(extra.lower()[:10]):
                    # Regenerativ / Gebäude gibi uzantı: sadece query tam eşleşmiyorsa atla
                    if abs(len(best.title) - len(title)) > 5:
                        return None
            return best
        return None
    return None


def _should_skip(row: dict) -> str | None:
    confidence = (row.get("confidence") or "").strip().lower()
    status = (row.get("status") or "unknown").strip()
    if confidence == "low" and status == "closed":
        return "low_confidence_closed"
    if status not in APPLY_STATUSES:
        return "invalid_status"
    return None


def apply_manual_research(
    path: Path,
    *,
    dry_run: bool = False,
    review_out: Path | None = None,
) -> dict:
    init_db()
    stats: dict[str, int] = {
        "rows": 0,
        "matched": 0,
        "updated": 0,
        "skipped": 0,
        "not_found": 0,
        "review_queue": 0,
    }
    details: list[dict] = []
    review_rows: list[dict] = []

    with path.open(encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]

    session = SessionLocal()
    try:
        for line in lines:
            stats["rows"] += 1
            row = json.loads(line)
            skip_reason = _should_skip(row)
            program = _find_program(session, row)
            if program is None:
                stats["not_found"] += 1
                details.append({"title": row.get("title"), "result": "not_found"})
                continue

            stats["matched"] += 1
            if skip_reason:
                stats["skipped"] += 1
                if skip_reason == "low_confidence_closed":
                    stats["review_queue"] += 1
                    review_rows.append({**row, "matched_title": program.title[:80]})
                details.append(
                    {
                        "title": program.title[:60],
                        "result": "skipped",
                        "reason": skip_reason,
                    }
                )
                continue

            status = row["status"].strip()
            old_status = program.status
            program.status = status
            canonical = (row.get("canonical_url") or "").strip() or None
            page_kind = (row.get("page_kind") or "").strip()
            # wrong_url + canonical yoksa veya canonical bozuk (... içeriyorsa) URL'yi bozma
            if (
                canonical
                and "..." not in canonical
                and canonical.rstrip("/") != (program.application_url or "").rstrip("/")
            ):
                program.application_url = canonical
            elif page_kind in {"wrong_url", "portal_root", "spa_shell"} and not canonical:
                logger.info(
                    "Status updated but URL left (no canonical): %s",
                    program.title[:50],
                )

            stats["updated"] += 1
            details.append(
                {
                    "title": program.title[:60],
                    "result": "updated",
                    "was": old_status,
                    "now": status,
                    "url": program.application_url,
                    "confidence": row.get("confidence"),
                }
            )
            logger.info(
                "%s: %s → %s (confidence=%s)",
                program.title[:50],
                old_status,
                status,
                row.get("confidence"),
            )

        if dry_run:
            session.rollback()
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if review_out and review_rows:
        review_out.parent.mkdir(parents=True, exist_ok=True)
        with review_out.open("w", encoding="utf-8") as fh:
            for row in review_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {"stats": stats, "details": details}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manuel JSONL araştırma sonuçlarını DB'ye yaz")
    parser.add_argument("jsonl", type=Path, help="manual_research JSONL dosyası")
    parser.add_argument("--dry-run", action="store_true", help="DB yazma, sadece rapor")
    parser.add_argument(
        "--review-out",
        type=Path,
        default=Path("review_queue.jsonl"),
        help="low confidence closed kayıtları",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    if not args.jsonl.exists():
        logger.error("Dosya bulunamadı: %s", args.jsonl)
        return 1

    report = apply_manual_research(
        args.jsonl,
        dry_run=args.dry_run,
        review_out=args.review_out,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
