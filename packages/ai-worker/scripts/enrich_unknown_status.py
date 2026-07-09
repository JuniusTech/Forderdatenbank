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


def _make_client(use_browser: bool):
    if not use_browser:
        return None, None
    from ingest.browser_client import PlaywrightClient

    client = PlaywrightClient()
    client.__enter__()
    return client, client


def enrich_unknown(
    *,
    limit: int = 50,
    delay_sec: float = 1.0,
    apply: bool = False,
    dry_run: bool = False,
    use_ai: bool = False,
    use_browser: bool = False,
    timeout: float = 30.0,
    checkpoint: int = 10,
) -> dict:
    init_db()
    stats: Counter[str] = Counter()
    checked = 0
    updates: list[dict] = []
    row_count = 0
    client, cleanup = _make_client(use_browser)

    try:
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
            row_count = len(rows)
            logger.info("İşlenecek unknown kayıt: %d (browser=%s, ai=%s)", row_count, use_browser, use_ai)

            for idx, program in enumerate(rows, start=1):
                url = (program.application_url or "").strip()
                if not url or not needs_live_check(program.status):
                    stats["skipped"] += 1
                    continue

                checked += 1
                live = check_live_url(
                    url,
                    client=client,
                    timeout=timeout,
                    program_title=program.title,
                    use_ai_fallback=use_ai,
                )
                stats[live.status] += 1
                entry = {
                    "title": program.title[:80],
                    "url": url,
                    "was": program.status,
                    "live": live.status,
                    "method": live.method,
                    "reason": live.reason,
                    "closure_date": live.closure_date.isoformat() if live.closure_date else None,
                    "funding_period": live.funding_period,
                    "evidence": live.evidence_quote,
                    "canonical_url": live.canonical_url,
                    "redirect_type": live.redirect_type,
                }
                updates.append(entry)

                if apply and not dry_run and live.status in {"closed", "active", "laufend"}:
                    program.status = live.status
                    if live.canonical_url and live.canonical_url.rstrip("/") != url.rstrip("/"):
                        program.application_url = live.canonical_url
                    stats["db_updated"] += 1

                logger.info(
                    "[%d/%d] %s → %s (%s)",
                    idx,
                    row_count,
                    program.title[:50],
                    live.status,
                    live.method,
                )

                # Periyodik commit — iptal edilse bile ilerleme kalıcı olsun
                if apply and not dry_run and checkpoint > 0 and checked % checkpoint == 0:
                    session.commit()
                    logger.info("  ↳ checkpoint commit (%d kayıt işlendi)", checked)

                if delay_sec > 0:
                    time.sleep(delay_sec)

            if apply and not dry_run:
                session.commit()
    finally:
        if cleanup is not None:
            cleanup.close()

    return {
        "candidates": row_count,
        "checked": checked,
        "distribution": dict(stats),
        "samples": updates[:10],
        "all": updates,
        "still_unknown": [u for u in updates if u["live"] == "unknown"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nur status=unknown Programme per Live-URL prüfen"
    )
    parser.add_argument("--limit", type=int, default=50, help="Max Programm (default 50)")
    parser.add_argument("--delay", type=float, default=1.0, help="Sekunden zwischen Requests")
    parser.add_argument("--apply", action="store_true", help="Live-Ergebnis in DB schreiben")
    parser.add_argument("--dry-run", action="store_true", help="Nur report, kein DB write")
    parser.add_argument("--ai", action="store_true", help="Regex unknown ise Ollama/Claude ile analiz et")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Playwright ile JS-render fetch (statik HTML görmeyen sayfalar için)",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Sayfa fetch timeout (sn)")
    parser.add_argument("--checkpoint", type=int, default=10, help="Her N kayıtta DB commit (0=kapalı)")
    parser.add_argument("--out", type=str, default=None, help="Tam sonucu JSON dosyasına yaz")
    parser.add_argument(
        "--unknown-out",
        type=str,
        default=None,
        help="Sadece hâlâ unknown kalan kayıtları JSONL olarak yaz (manuel araştırma için)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    report = enrich_unknown(
        limit=args.limit,
        delay_sec=args.delay,
        apply=args.apply,
        dry_run=args.dry_run,
        use_ai=args.ai,
        use_browser=args.browser,
        timeout=args.timeout,
        checkpoint=args.checkpoint,
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report["all"], fh, indent=2, ensure_ascii=False)
        print(f"Tam sonuç yazıldı: {args.out} ({len(report['all'])} kayıt)")

    if args.unknown_out:
        with open(args.unknown_out, "w", encoding="utf-8") as fh:
            for row in report["still_unknown"]:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            f"Kalan unknown yazıldı: {args.unknown_out} "
            f"({len(report['still_unknown'])} kayıt)"
        )

    summary = {k: v for k, v in report.items() if k not in {"all", "still_unknown"}}
    print("\n=== UNKNOWN LIVE ENRICHMENT ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
