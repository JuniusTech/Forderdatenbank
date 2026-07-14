"""DB'deki status=unknown kayıtlarını export et + HTTP0/ollama_stuck kırılımı."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from ai.site_profiles import url_is_insufficient
from db.models import FundingProgram
from db.session import get_session, init_db


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _load_monitor_index(path: Path) -> dict[str, dict]:
    """URL → en son live_monitor satırı (run özetlerindeki still_unknown/all)."""
    index: dict[str, dict] = {}
    if not path.is_file():
        return index
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                run = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Run-level wrapper
            if isinstance(run, dict) and ("still_unknown" in run or "all" in run):
                checked_at = run.get("run_started") or run.get("at")
                for row in run.get("still_unknown") or []:
                    url = (row.get("url") or "").strip().rstrip("/")
                    if not url:
                        continue
                    entry = dict(row)
                    if checked_at and not entry.get("checked_at"):
                        entry["checked_at"] = checked_at
                    index[url] = entry
                for row in run.get("all") or []:
                    if row.get("live") != "unknown":
                        continue
                    url = (row.get("url") or "").strip().rstrip("/")
                    if not url:
                        continue
                    entry = dict(row)
                    if checked_at and not entry.get("checked_at"):
                        entry["checked_at"] = checked_at
                    index[url] = entry
                continue
            # Düz satır (eski format)
            url = (run.get("url") or "").strip().rstrip("/")
            if url:
                index[url] = run
    return index


def _classify(*, reason: str, method: str, url: str, http_status: int | None) -> str:
    reason_l = (reason or "").lower()
    method_l = (method or "").lower()

    if http_status == 0 or "http 0" in reason_l or "nicht erreichbar" in reason_l:
        return "http0"
    if http_status == 403 or "http 403" in reason_l:
        return "http403"
    if http_status in {404, 410} or "http 404" in reason_l or "http 410" in reason_l:
        return "http404"
    if url_is_insufficient(url):
        return "wrong_url"
    if method_l.startswith("ollama"):
        return "ollama_stuck"
    if method_l == "regex":
        return "regex_stuck"
    return "other"


def export_kalan(
    *,
    monitor_log: Path,
    out_jsonl: Path,
    summary_out: Path | None = None,
) -> dict:
    init_db()
    monitor = _load_monitor_index(monitor_log)
    now = datetime.now(timezone.utc).isoformat()

    rows_out: list[dict] = []
    bucket: Counter[str] = Counter()
    bucket_hosts: dict[str, Counter[str]] = defaultdict(Counter)

    with get_session() as session:
        programs = list(
            session.scalars(
                select(FundingProgram)
                .where(FundingProgram.status == "unknown")
                .where(FundingProgram.application_url.is_not(None))
                .where(FundingProgram.application_url != "")
                .order_by(FundingProgram.title)
            ).all()
        )

        for prog in programs:
            url = (prog.application_url or "").strip()
            prev = monitor.get(url.rstrip("/"), {})
            reason = prev.get("reason") or ""
            method = prev.get("method") or "none"
            http_status = prev.get("http_status")
            if http_status is None and "HTTP " in reason:
                try:
                    http_status = int(reason.split("HTTP ", 1)[1].split(":", 1)[0].split()[0])
                except (ValueError, IndexError):
                    http_status = None

            bucket_key = _classify(
                reason=reason,
                method=method,
                url=url,
                http_status=http_status,
            )
            bucket[bucket_key] += 1
            bucket_hosts[bucket_key][_host(url)] += 1

            rows_out.append(
                {
                    "title": prog.title,
                    "url": url,
                    "was": "unknown",
                    "live": "unknown",
                    "changed": False,
                    "method": method if prev else "none",
                    "reason": reason or "(no prior live check)",
                    "closure_date": prev.get("closure_date"),
                    "funding_period": prev.get("funding_period"),
                    "evidence": prev.get("evidence") or prev.get("evidence_quote"),
                    "canonical_url": prev.get("canonical_url"),
                    "redirect_type": prev.get("redirect_type"),
                    "bucket": bucket_key,
                    "host": _host(url),
                    "checked_at": prev.get("checked_at") or prev.get("at"),
                    "exported_at": now,
                }
            )

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as fh:
        for row in rows_out:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    host_totals = Counter(r["host"] for r in rows_out)
    summary = {
        "exported_at": now,
        "total": len(rows_out),
        "buckets": dict(bucket),
        "top_hosts": host_totals.most_common(30),
        "bucket_top_hosts": {
            k: v.most_common(15) for k, v in sorted(bucket_hosts.items())
        },
        "monitor_log": str(monitor_log),
        "out_jsonl": str(out_jsonl),
        "with_prior_check": sum(1 for r in rows_out if r["method"] != "none"),
        "without_prior_check": sum(1 for r in rows_out if r["method"] == "none"),
    }

    if summary_out:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        with summary_out.open("w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export DB unknown → kalan_unknown.jsonl")
    parser.add_argument(
        "--monitor-log",
        type=Path,
        default=Path("logs/live_monitor.jsonl"),
        help="Önceki live check sonuçları (sınıflandırma için)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("kalan_unknown.jsonl"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("logs/kalan_unknown_summary.json"),
    )
    args = parser.parse_args(argv)

    summary = export_kalan(
        monitor_log=args.monitor_log,
        out_jsonl=args.out,
        summary_out=args.summary,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
