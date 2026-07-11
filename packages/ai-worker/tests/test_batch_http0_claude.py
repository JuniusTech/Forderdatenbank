"""Claude HTTP0 batch — closed/hijack/domain rule regresyon."""

from datetime import date
from unittest.mock import patch

from ingest.domain_rules import expand_url_variants, is_suspicious_redirect
from ingest.live_status import check_live_url

REF = date(2026, 7, 10)


def _check(html: str, *, url: str = "https://example.de/p"):
    with patch("ingest.live_status.HttpClient") as mock_client:
        mock_client.return_value.get.return_value = (200, url, html)
        return check_live_url(url, reference=REF, use_ai_fallback=False)


def test_mittel_ausgeschoepft_closed():
    html = """
    <html><body>
    Die zur Verfügung stehenden Mittel im Digitalbonus sind ausgeschöpft.
    Eine Antragstellung ist daher nicht mehr möglich.
    </body></html>
    """
    assert _check(html).status == "closed"


def test_derzeit_antragstellung_nicht_moeglich_closed():
    html = """
    <html><body>
    Derzeit ist eine Antragstellung in dieser Förderrichtlinie nicht möglich.
    </body></html>
    """
    assert _check(html).status == "closed"


def test_seit_datum_antragsstellung_closed():
    html = """
    <html><body>
    Eine Antragsstellung ist seit dem 01.01.2026 nicht mehr möglich.
    </body></html>
    """
    assert _check(html).status == "closed"


def test_tab_online_portal_active():
    html = """
    <html><body>
    Die Antragstellung für die Beratungsrichtlinie ist über das Online-Portal der TAB möglich.
    </body></html>
    """
    assert _check(html).status == "active"


def test_brandenburg_go_hijack_detected():
    assert is_suspicious_redirect(
        "https://www.brandenburg-go.de/",
        "https://travelerzdeal.com/offers",
    )


def test_aufbaubank_lowercase_variant():
    variants = expand_url_variants(
        "https://www.aufbaubank.de/Foerderprogramme/Beratungsrichtlinie"
    )
    assert any("/foerderprogramme/beratungsrichtlinie" in v for v in variants)
