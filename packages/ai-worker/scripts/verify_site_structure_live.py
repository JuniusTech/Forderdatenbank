"""Site-structure araştırma URL'lerini Playwright+AI ile canlı doğrula."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Tercih edilen mevcut model
os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:14b-instruct")
os.environ.setdefault("LIVE_CHECK_AI_PROVIDER", "ollama")

from ingest.browser_client import PlaywrightClient
from ingest.live_status import check_live_url

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "manual_research_site_structure.jsonl",
    ROOT / "manual_research_site_structure_part2.jsonl",
]


def load_cases() -> list[dict]:
    cases: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path in FILES:
        if not path.exists():
            print(f"SKIP missing {path.name}", file=sys.stderr)
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if "typical_page_kind" in row and "title" not in row:
                continue
            title = (row.get("title") or "").strip()
            url = (row.get("canonical_url") or row.get("url") or "").strip()
            if not url or "..." in url:
                url = (row.get("url") or "").strip()
            if not url or not title:
                continue
            key = (title[:80], url)
            if key in seen:
                continue
            seen.add(key)
            cases.append(
                {
                    "domain": row.get("domain"),
                    "title": title,
                    "url": url,
                    "expected": (row.get("status") or "unknown").strip(),
                    "page_kind": row.get("page_kind"),
                    "confidence": row.get("confidence"),
                }
            )
    return cases


def main() -> int:
    cases = load_cases()
    print(f"Testing {len(cases)} cases with Playwright + Ollama...\n")
    results: list[dict] = []

    with PlaywrightClient(render_wait_ms=2500) as client:
        for i, case in enumerate(cases, 1):
            print(f"[{i}/{len(cases)}] {case['domain']}: {case['title'][:55]}…", flush=True)
            try:
                live = check_live_url(
                    case["url"],
                    client=client,
                    program_title=case["title"],
                    use_ai_fallback=True,
                    timeout=45.0,
                )
            except Exception as exc:
                live_status = "error"
                reason = f"{exc.__class__.__name__}: {exc}"
                method = "error"
                http = 0
            else:
                live_status = live.status
                reason = (live.reason or "")[:160]
                method = live.method or ""
                http = live.http_status

            ok = live_status == case["expected"]
            # Hub/wrong_url: pipeline unknown, research active = kısmen beklenen
            soft = (
                not ok
                and case["expected"] == "active"
                and live_status == "unknown"
                and case.get("page_kind") in {"wrong_url", "portal_root", "spa_shell", "ministry_overview"}
            )
            mark = "OK" if ok else ("SOFT" if soft else "FAIL")
            print(
                f"  -> {mark} expected={case['expected']} got={live_status} "
                f"http={http} method={method}",
                flush=True,
            )
            results.append(
                {
                    **case,
                    "got": live_status,
                    "http": http,
                    "method": method,
                    "reason": reason,
                    "mark": mark,
                }
            )

    out = ROOT / "site_structure_live_verify.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    counts = {k: sum(1 for r in results if r["mark"] == k) for k in ("OK", "SOFT", "FAIL")}
    print("\n=== SUMMARY ===")
    print(counts)
    print(f"Wrote {out}")
    if counts["FAIL"]:
        print("\nFAILS:")
        for r in results:
            if r["mark"] == "FAIL":
                print(
                    f"- {r['domain']}: {r['title'][:50]} | "
                    f"exp={r['expected']} got={r['got']} | {r['reason'][:100]}"
                )
    return 0 if counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
