"""Batch 1 manuel araştırma — pipeline regresyon testi (Claude eklentisi ground-truth)."""

from datetime import date
from unittest.mock import patch

from ingest.live_status import apply_live_heuristics, check_live_url, scan_live_text

REF = date(2026, 7, 9)


def _check(html: str, *, url: str, final_url: str | None = None, status_code: int = 200):
    final = final_url or url
    with patch("ingest.live_status.HttpClient") as mock_client:
        mock_client.return_value.get.return_value = (status_code, final, html)
        return check_live_url(url, reference=REF, use_ai_fallback=False)


def test_batch1_akz_online_antrag_active():
    html = """
    <html><body>
    Ausbildungskostenzuschuss für Benachteiligte (AKZ).
    Hier können Sie den Online-Antrag stellen: https://foerderverfahren.hessen.de/
    Staatsanzeiger Nr. 26/2023.
    </body></html>
    """
    result = _check(html, url="https://rp-kassel.hessen.de/.../ausbildungskostenzuschuss-fuer-benachteiligte")
    assert result.status == "active"


def test_batch1_agz_redirect_canonical():
    old = "https://umwelt.hessen.de/landwirtschaft/foerderungen/ausgleichszulage-agz"
    new = "https://landwirtschaft.hessen.de/landwirtschaft/foerderungen/ausgleichszulage-agz"
    html = """
    <html><body>
    Ausgleichszulage für benachteiligte Gebiete (AGZ).
    Ab dem Jahr 2025 werden alle förderfähigen hessischen Flächen gefördert.
    Antrag bei den Landratsämtern.
    </body></html>
    """
    result = _check(html, url=old, final_url=new)
    assert result.status == "active"
    assert result.canonical_url == new


def test_batch1_asaar_antragsformular_active():
    html = """
    <html><body>
    Arbeit für das Saarland (ASaar) — Landesprogramm mit fünf Förderschwerpunkten.
  Downloads: Antragsformular Landesmittel (PDF).
    </body></html>
    """
    result = _check(html, url="https://www.saarland.de/.../asaar.html")
    assert result.status == "active"


def test_batch1_assistierte_reproduktion_closed():
    html = """
    <html><body>
    <h2>Wichtige Information!</h2>
    Aufgrund der Haushaltslage können keine neuen Anträge mehr auf Förderung gestellt werden.
    Nur noch Abwicklung offener Altfälle.
    </body></html>
    """
    result = _check(html, url="https://www.berlin.de/.../foerderung-kinderwunsch/")
    assert result.status == "closed"


def test_batch1_aktion100_laufendes_programm_active():
    html = """
    <html><body>
    Seit 18 Jahren unterstützt das Förderprogramm "Aktion 100" junge Menschen mit Behinderung.
    Kontakt über Reha-Beratung der Arbeitsagentur.
    </body></html>
    """
    result = _check(html, url="https://www.mags.nrw/ausbildung-mit-behinderung")
    assert result.status == "active"
