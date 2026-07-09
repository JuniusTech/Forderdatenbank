"""Manuel ground-truth (10 kayıt) — karar kuralları regresyon testi."""

from datetime import date
from unittest.mock import patch

from ingest.live_status import LiveStatusResult, check_live_url, detect_error_page, apply_live_heuristics

REF = date(2026, 7, 8)


def _check(html: str, *, url: str, final_url: str | None = None, status_code: int = 200):
    final = final_url or url
    with patch("ingest.live_status.HttpClient") as mock_client:
        mock_client.return_value.get.return_value = (status_code, final, html)
        return check_live_url(url, reference=REF, use_ai_fallback=False)


def test_ground_truth_404_closed():
    result = _check("<html><body>404</body></html>", url="https://example.de/missing", status_code=404)
    assert result.status == "closed"
    assert "404" in result.reason


def test_ground_truth_lbank_error_page_closed():
    html = "<html><head><title>Fehlerseite</title></head><body>Kein Programminhalt</body></html>"
    result = _check(html, url="https://www.l-bank.de/old-program.html")
    assert result.status == "closed"
    assert "Fehlerseite" in result.reason


def test_ground_truth_ilb_validity_laufend():
    html = """
    <html><body>
    Die Richtlinie ist bis zum 31. Dezember 2028 gültig.
    Behindertengerechte Anpassung von vorhandenem Wohnraum.
    </body></html>
    """
    result = _check(html, url="https://www.ilb.de/programm/")
    assert result.status == "laufend"
    assert result.closure_date == date(2028, 12, 31)


def test_ground_truth_kfw_partner_bank_active():
    html = """
    <html><body>
    Absicherungsinstrument für Transformationsindustrien.
    Bitte wenden Sie sich an Ihren Finanzierungspartner.
    Die Beteiligung der KfW erfolgt auf Einladung Ihres Finanzierungspartners.
    Konditionen und Voraussetzungen für das Förderprodukt.
    </body></html>
    """
    result = _check(html, url="https://www.kfw.de/product/")
    assert result.status == "active"
    assert "Finanzierungspartner" in result.reason


def test_ground_truth_rentenbank_redirect_consolidated():
    html = """
    <html><body>
    Stand: 1. Juli 2026
    Die Förderung ist befristet bis längstens 30. Juni 2027.
    Agrarnahe Unternehmen — Übersicht aller Förderkredite.
    </body></html>
    """
    old = "https://www.rentenbank.de/programmkredite/agrar/betriebsmittel/"
    new = "https://www.rentenbank.de/foerderkredite/agrarnahe-unternehmen/"
    result = _check(html, url=old, final_url=new)
    assert result.status == "laufend"
    assert result.canonical_url == new
    assert result.redirect_type == "consolidated"
    assert result.closure_date == date(2027, 6, 30)


def test_ground_truth_mags_rolling_active_heuristic():
    text = """
    Aktion 100 — seit 2007 laufendes Programm für Jugendliche mit Behinderung.
    Kontakt über Reha-Beratung der Agentur für Arbeit.
    """
    hit = apply_live_heuristics(text, reference=REF)
    assert hit is not None
    assert hit[0] == "active"


def test_ground_truth_detect_error_page_title():
    html = "<html><head><title>Fehlerseite</title></head><body></body></html>"
    hit = detect_error_page(html=html, text="")
    assert hit is not None
    assert hit[0] == "closed"


def test_ground_truth_unreachable_stays_unknown():
    with patch("ingest.live_status.HttpClient") as mock_client:
        import requests

        mock_client.return_value.get.side_effect = requests.exceptions.Timeout()
        result = check_live_url("https://example.de/", reference=REF)
    assert result.status == "unknown"
