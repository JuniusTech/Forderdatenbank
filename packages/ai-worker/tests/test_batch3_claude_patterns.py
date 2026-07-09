"""Claude kalan19 — yeni regex kuralları regresyon testi."""

from datetime import date
from unittest.mock import patch

from ingest.live_status import apply_live_heuristics, check_live_url

REF = date(2026, 7, 9)


def _check(html: str, *, url: str = "https://example.de/p"):
    with patch("ingest.live_status.HttpClient") as mock_client:
        mock_client.return_value.get.return_value = (200, url, html)
        return check_live_url(url, reference=REF, use_ai_fallback=False)


def test_alpha_plus_rolling_frist_active():
    html = """
    <html><body>
    Die Antragsfrist beträgt 2 Woche(n). Der Antrag auf Zuwendung ist spätestens
    zwei Wochen vor dem geplanten Kursbeginn einzureichen.
    </body></html>
    """
    assert _check(html).status == "active"


def test_nbank_antragsstichtag_laufend():
    html = """
    <html><body>
    Landschaftswerte 2.0 — Der nächste Antragsstichtag ist am 30.09.2026.
    </body></html>
    """
    result = _check(html)
    assert result.status == "laufend"
    assert result.closure_date == date(2026, 9, 30)


def test_aufbaubank_foerderportal_active():
    html = """
    <html><body>
    Gigabitrichtlinie — Die Antragstellung ist über das Förderportal möglich.
    </body></html>
    """
    assert _check(html).status == "active"


def test_fischerei_jederzeit_active():
    html = """
    <html><body>
    Fördermöglichkeiten Fischerei — eine Antragstellung ist hier jederzeit möglich.
    </body></html>
    """
    assert _check(html).status == "active"


def test_wtsh_digitale_antrag_active():
    html = """
    <html><body>
    Wasserstoffrichtlinie — Die digitale Antragstellung ist in Kürze möglich.
    </body></html>
    """
    assert _check(html).status == "active"


def test_lfa_auftragsgarantie_active():
    text = "Mit unseren Auftragsgarantien bieten wir dafür ein flexibles Instrument an."
    hit = apply_live_heuristics(text, reference=REF)
    assert hit is not None
    assert hit[0] == "active"
