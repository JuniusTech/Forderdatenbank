"""Batch 1 URL'leri canlı pipeline ile doğrula (regex only, AI yok)."""

from datetime import date

from ingest.live_status import check_live_url

BATCH1 = [
    ("AKZ", "https://rp-kassel.hessen.de/soziales/ausbildungs-und-arbeitsmarkfoerderung/ausbildungskostenzuschuss-fuer-benachteiligte", "active"),
    ("AGZ", "https://umwelt.hessen.de/landwirtschaft/foerderungen/ausgleichszulage-agz", "active"),
    ("ASaar", "https://www.saarland.de/masfg/DE/portale/arbeit/instrumentederarbeitsmarktpolitik/asaar.html", "active"),
    ("Assistierte Reproduktion", "https://www.berlin.de/lageso/soziales/zuwendung/foerderung-kinderwunsch/", "closed"),
    ("Aktion 100", "https://www.mags.nrw/ausbildung-mit-behinderung", "active"),
]

REF = date(2026, 7, 9)


def main() -> None:
    print("=== Canlı URL doğrulama (regex, browser yok) ===\n")
    ok = 0
    for label, url, expected in BATCH1:
        result = check_live_url(url, reference=REF, use_ai_fallback=False, timeout=30.0)
        match = result.status == expected
        ok += int(match)
        icon = "OK" if match else "FAIL"
        print(f"[{icon}] {label}: expected={expected} got={result.status} ({result.method})")
        print(f"      reason: {result.reason[:100]}")
        if result.canonical_url:
            print(f"      canonical: {result.canonical_url}")
        print()
    print(f"Sonuç: {ok}/{len(BATCH1)} eşleşti")


if __name__ == "__main__":
    main()
