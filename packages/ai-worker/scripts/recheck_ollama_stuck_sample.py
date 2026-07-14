"""Kalan unknown içinden ulaşılabilir top-domain örneklerini yeniden kontrol et."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:14b-instruct")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from ingest.browser_client import PlaywrightClient, strip_url_fragment
from ingest.live_status import check_live_url

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "projekttraeger.dlr.de",
    "bra.nrw.de",
    "efre.nrw.de",
    "mhkbd.nrw",
    "regioaktiv.sachsen-anhalt.de",
    "schleswig-holstein.de",
}


def load_samples(limit_per_host: int = 2) -> list[dict]:
    picked: dict[str, list] = {h: [] for h in TARGETS}
    with (ROOT / "kalan_unknown.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if (o.get("method") or "") not in {"ollama", "ollama+site"}:
                continue
            host = urlparse(o["url"]).netloc.lower().removeprefix("www.")
            if host not in TARGETS or len(picked[host]) >= limit_per_host:
                continue
            # SH: skip known insufficient vi_node for this sample if we already have one
            path = urlparse(o["url"]).path.lower()
            if host == "schleswig-holstein.de" and ("vi_node" in path or "viii_node" in path):
                continue
            picked[host].append(o)
    out: list[dict] = []
    for items in picked.values():
        out.extend(items)
    return out


def main() -> int:
    samples = load_samples(2)
    print(f"Re-check {len(samples)} ollama-stuck samples...\n")
    ok = fail = 0
    with PlaywrightClient(render_wait_ms=2500) as client:
        for i, row in enumerate(samples, 1):
            title = (row.get("title") or "")[:55]
            url = strip_url_fragment(row["url"])
            host = urlparse(url).netloc.lower().removeprefix("www.")
            print(f"[{i}/{len(samples)}] {host}: {title}...", flush=True)
            live = check_live_url(
                url,
                client=client,
                program_title=row.get("title") or "",
                use_ai_fallback=True,
                timeout=45.0,
            )
            changed = live.status != "unknown"
            mark = "RESOLVED" if changed else "STILL_UNKNOWN"
            if changed:
                ok += 1
            else:
                fail += 1
            print(
                f"  -> {mark} status={live.status} http={live.http_status} "
                f"method={live.method}",
                flush=True,
            )
            print(f"     {(live.reason or '')[:130]}", flush=True)
    print(f"\n=== SAMPLE RECHECK === resolved={ok} still_unknown={fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
