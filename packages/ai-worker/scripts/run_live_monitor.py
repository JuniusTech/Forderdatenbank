"""Zamanlanmış canlı URL izleyici — Playwright + regex + AI fallback."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from ingest.live_monitor import run_live_monitor

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Förderprogramm application_url canlı izleme")
    parser.add_argument(
        "--mode",
        choices=("unknown", "active", "all"),
        default="unknown",
        help="unknown=öncelik unknown, active=re-check active/laufend, all=hepsi",
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--delay", type=float, default=1.5, help="İstekler arası bekleme (sn)")
    parser.add_argument("--apply", action="store_true", help="Değişiklikleri DB'ye yaz")
    parser.add_argument("--dry-run", action="store_true", help="Sadece rapor")
    parser.add_argument("--no-ai", action="store_true", help="Ollama/Claude fallback kapalı")
    parser.add_argument("--no-browser", action="store_true", help="requests kullan (Playwright kapalı)")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--checkpoint", type=int, default=10)
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("logs/live_monitor.jsonl"),
        help="Run geçmişi JSONL (append)",
    )
    parser.add_argument("--out", type=Path, default=None, help="Bu run'ın tam JSON raporu")
    parser.add_argument(
        "--unknown-out",
        type=Path,
        default=None,
        help="Hâlâ unknown kalan kayıtları JSONL yaz",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    report = run_live_monitor(
        mode=args.mode,
        limit=args.limit,
        delay_sec=args.delay,
        apply=args.apply,
        dry_run=args.dry_run,
        use_ai=not args.no_ai,
        use_browser=not args.no_browser,
        timeout=args.timeout,
        checkpoint=args.checkpoint,
        log_path=args.log,
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            json.dump(report["all"], fh, indent=2, ensure_ascii=False)
        print(f"Rapor: {args.out} ({len(report['all'])} kayıt)")

    if args.unknown_out:
        args.unknown_out.parent.mkdir(parents=True, exist_ok=True)
        with args.unknown_out.open("w", encoding="utf-8") as fh:
            for row in report["still_unknown"]:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Unknown: {args.unknown_out} ({len(report['still_unknown'])} kayıt)")

    summary = {k: v for k, v in report.items() if k not in {"all", "still_unknown", "changed"}}
    summary["changed_count"] = len(report["changed"])
    print("\n=== LIVE MONITOR ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
