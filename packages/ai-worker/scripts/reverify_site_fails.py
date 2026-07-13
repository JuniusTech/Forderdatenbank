"""Sadece önceki FAIL vakalarını yeniden doğrula."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:14b-instruct")
os.environ.setdefault("LIVE_CHECK_AI_PROVIDER", "ollama")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from ingest.browser_client import PlaywrightClient
from ingest.live_status import check_live_url

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "site_structure_live_verify.jsonl"

# FAIL listesinden yeniden dene (SOFT/OK atla); URL DB düzeltmeleri dahil
CASES = [
    {
        "domain": "schleswig-holstein.de",
        "title": "Eingliederung von Gefangenen durch Arbeit und Qualifizierung (AQUA)",
        "url": "https://www.schleswig-holstein.de/DE/fachinhalte/J/justizvollzug/bildungsmassnahmen.html",
        "expected": "laufend",
    },
    {
        "domain": "lvwa.sachsen-anhalt.de",
        "title": "Förderung der Einheiten des Katastrophenschutzes im Land Sachsen-Anhalt",
        "url": "https://lvwa.sachsen-anhalt.de/das-lvwa/kommunales-ordnung-verbraucherschutz-migration/brand-und-katastrophenschutz-militaerische-angelegenheiten-rettungswesen/foerdermittel-katastrophenschutz/",
        "expected": "active",
    },
    {
        "domain": "lvwa.sachsen-anhalt.de",
        "title": "Förderung der inhaltlichen Arbeit in Frauenhäusern und deren ambulanten Beratung",
        "url": "https://lvwa.sachsen-anhalt.de/das-lvwa/landesjugendamt/familien-und-frauen/frauenfoerderung",
        "expected": "unknown",
    },
    {
        "domain": "umwelt.nrw.de",
        "title": "Förderrichtlinien Biologische Stationen NRW (FöBS)",
        "url": "https://www.umwelt.nrw.de/naturschutz/wer-macht-was/biologische-stationen/",
        "expected": "active",
    },
    {
        "domain": "mags.nrw",
        "title": "Beschäftigtentransfer (Förderung von Transfergesellschaften)",
        "url": "https://www.mags.nrw/beschaeftigtentransfer",
        "expected": "active",
    },
    {
        "domain": "mags.nrw",
        "title": "Förderrichtlinie für Hausärztinnen und Hausärzte",
        "url": "https://www.mags.nrw/hausarztaktionsprogramm",
        "expected": "active",
    },
    {
        "domain": "mags.nrw",
        "title": "Förderrichtlinie Gesundheitsfachberufe",
        "url": "https://www.mags.nrw/einstieg-schulgeldfreiheit",
        "expected": "active",
    },
    {
        "domain": "aufbaubank.de",
        "title": "Förderrichtlinie ESF Plus Fachkräftesicherung und gesellschaftliche Teilhabe – Gründungsrichtlinie",
        "url": "https://www.aufbaubank.de/Foerderprogramme/Gruendungsrichtlinie",
        "expected": "active",
    },
    {
        "domain": "aufbaubank.de",
        "title": "Förderrichtlinie Trinkwasserinfrastruktur ländlicher Raum",
        "url": "https://www.aufbaubank.de/Foerderprogramme/Trinkwasserfoerderung",
        "expected": "active",
    },
    {
        "domain": "aufbaubank.de",
        "title": "Förderung der Forschung (FTI-Thüringen FORSCHUNG)",
        "url": "https://www.aufbaubank.de/Foerderprogramme/FTI-Thueringen-FORSCHUNG",
        "expected": "active",
    },
    {
        "domain": "foerderportal.wibank.de",
        "title": "Bürgschaften zur Sicherung von Investitionen in Wohngebäuden",
        "url": "https://www.wibank.de/resource/blob/wibank-richtlinie-buergschaft-data",
        "expected": "unknown",  # kırık blob → artık closed değil
    },
]


def main() -> int:
    print(f"Re-verify {len(CASES)} former FAILs...\n")
    ok = soft = fail = 0
    with PlaywrightClient(render_wait_ms=2500) as client:
        for i, case in enumerate(CASES, 1):
            print(f"[{i}/{len(CASES)}] {case['domain']}: {case['title'][:50]}...", flush=True)
            live = check_live_url(
                case["url"],
                client=client,
                program_title=case["title"],
                use_ai_fallback=True,
                timeout=90.0,
            )
            mark = "OK" if live.status == case["expected"] else "FAIL"
            if mark == "OK":
                ok += 1
            else:
                fail += 1
            print(
                f"  -> {mark} exp={case['expected']} got={live.status} "
                f"http={live.http_status} method={live.method}",
                flush=True,
            )
            print(f"     {(live.reason or '')[:140]}", flush=True)
    print(f"\n=== RE-VERIFY === OK={ok} FAIL={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
