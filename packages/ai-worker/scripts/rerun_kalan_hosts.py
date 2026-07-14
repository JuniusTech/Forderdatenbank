"""kalan_unknown içinden belirli domain'leri yeniden canlı kontrol + DB apply."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:14b-instruct")

from sqlalchemy import select

from db.models import FundingProgram
from db.session import SessionLocal, init_db
from ingest.browser_client import PlaywrightClient, strip_url_fragment
from ingest.live_status import check_live_url

logger = logging.getLogger(__name__)

DEFAULT_HOSTS = (
    "projekttraeger.dlr.de",
    "bra.nrw.de",
    "efre.nrw.de",
    "mhkbd.nrw",
    "regioaktiv.sachsen-anhalt.de",
)

BATCH2_HOSTS = (
    "schleswig-holstein.de",
    "lfa.de",
    "soziales.niedersachsen.de",
    "lvwa.sachsen-anhalt.de",
    "mwl.sachsen-anhalt.de",
    "hamburg.de",
)


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def find_program(session, title: str, url: str) -> FundingProgram | None:
    """Önce title (paylaşılan portal kökü için kritik), sonra URL."""
    if title:
        exact = session.scalar(
            select(FundingProgram).where(FundingProgram.title == title).limit(1)
        )
        if exact:
            return exact
        # Encoding bozulması (?, …) için prefix
        soft = session.scalar(
            select(FundingProgram)
            .where(FundingProgram.title.ilike(f"{title[:40]}%"))
            .limit(1)
        )
        if soft:
            return soft
    if url:
        # Aynı URL birden fazla programda olabilir → yalnız tek adaya izin ver
        matches = session.scalars(
            select(FundingProgram).where(FundingProgram.application_url == url)
        ).all()
        if len(matches) == 1:
            return matches[0]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", type=Path, default=Path("kalan_unknown.jsonl"))
    parser.add_argument("--hosts", nargs="*", default=list(DEFAULT_HOSTS))
    parser.add_argument(
        "--batch2",
        action="store_true",
        help="Batch2: SH + lfa + Nds + SA + Hamburg",
    )
    parser.add_argument("--limit", type=int, default=0, help="0 = all matching")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    hosts = {h.lower().removeprefix("www.") for h in (BATCH2_HOSTS if args.batch2 else args.hosts)}

    rows: list[dict] = []
    with args.jsonl.open(encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if host_of(o.get("url") or "") in hosts:
                rows.append(o)
    if args.limit:
        rows = rows[: args.limit]

    print(f"Targets: {len(rows)} from {sorted(hosts)}")
    init_db()
    stats = {"checked": 0, "resolved": 0, "updated": 0, "by_status": {}}

    session = SessionLocal()
    try:
        with PlaywrightClient(render_wait_ms=2500) as client:
            for i, row in enumerate(rows, 1):
                title = row.get("title") or ""
                url = strip_url_fragment(row.get("url") or "")
                print(f"[{i}/{len(rows)}] {title[:55]}...", flush=True)
                live = check_live_url(
                    url,
                    client=client,
                    program_title=title,
                    use_ai_fallback=True,
                    timeout=45.0,
                )
                stats["checked"] += 1
                stats["by_status"][live.status] = stats["by_status"].get(live.status, 0) + 1
                changed = live.status != "unknown"
                if changed:
                    stats["resolved"] += 1
                print(
                    f"  -> {live.status} ({live.method}) http={live.http_status}",
                    flush=True,
                )
                if args.apply and live.status in {"active", "closed", "laufend"}:
                    prog = find_program(session, title, url)
                    if prog and prog.status == "unknown":
                        prog.status = live.status
                        stats["updated"] += 1
                        if live.canonical_url and live.canonical_url.rstrip("/") != (
                            prog.application_url or ""
                        ).rstrip("/"):
                            prog.application_url = live.canonical_url
                        if i % 10 == 0:
                            session.commit()
                    elif not prog:
                        logger.warning("No DB match for: %s", title[:70])
                if args.delay:
                    import time

                    time.sleep(args.delay)
        if args.apply:
            session.commit()
    finally:
        session.close()

    print(json.dumps({"stats": stats, "at": datetime.now(timezone.utc).isoformat()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
