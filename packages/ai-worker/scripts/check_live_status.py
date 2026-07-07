"""Tek URL veya program için canlı sayfa status kontrolü."""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import select

import db.config  # noqa: F401 — .env yükle

from db.models import FundingProgram
from db.session import get_session, init_db
from ai.page_extractor import ai_fallback_available
from ingest.live_status import check_live_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Canlı Antragsseite status kontrolü")
    parser.add_argument("--url", help="Direkt URL (ör. IBB Programmseite)")
    parser.add_argument("--title", help="DB'de program başlığı ara")
    parser.add_argument("--apply", action="store_true", help="Live=closed ise DB status güncelle")
    parser.add_argument("--ai", action="store_true", help="Regex unknown ise Ollama/Claude ile analiz et")
    args = parser.parse_args(argv)

    url = args.url
    program_id = None
    xml_status = None

    program_title = ""

    if args.title:
        init_db()
        with get_session() as session:
            program = session.scalar(
                select(FundingProgram).where(FundingProgram.title.ilike(f"%{args.title}%")).limit(1)
            )
            if not program:
                print(f"Program bulunamadı: {args.title}")
                return 1
            program_id = program.id
            xml_status = program.status
            url = program.application_url
            program_title = program.title
            print(f"Program: {program.title}")
            print(f"XML status: {xml_status}")
            print(f"URL: {url}")

    if not url:
        parser.error("--url veya --title gerekli")

    result = check_live_url(
        url,
        program_title=program_title,
        use_ai_fallback=args.ai or ai_fallback_available(),
    )
    out = {
        "url": result.url,
        "final_url": result.final_url,
        "http_status": result.http_status,
        "live_status": result.status,
        "method": result.method,
        "reason": result.reason,
        "closure_date": result.closure_date.isoformat() if result.closure_date else None,
        "funding_period": result.funding_period,
        "confidence": result.confidence,
        "evidence_quote": result.evidence_quote,
        "snippet": result.snippet,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))

    if args.apply and program_id and xml_status == "unknown" and result.status in {"closed", "active", "laufend"}:
        with get_session() as session:
            row = session.get(FundingProgram, program_id)
            if row:
                row.status = result.status
                session.commit()
                print(f"DB güncellendi: unknown → {result.status}")
    elif args.apply and xml_status != "unknown":
        print(f"Live-Prüfung nur für unknown — XML status zaten '{xml_status}'")
    elif args.apply and result.status == "unknown":
        print("Live sonuç unknown — DB güncellenmedi")

    return 0


if __name__ == "__main__":
    sys.exit(main())
