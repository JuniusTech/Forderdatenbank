"""Batch 2 manuel araştırma — yanlış URL / parent-page retry regresyon testi."""

from datetime import date
from unittest.mock import patch

from ingest.live_status import _parent_url, _should_try_parent, check_live_url

REF = date(2026, 7, 9)


def _check(html: str, *, url: str, final_url: str | None = None, title: str = "", parent_html: str | None = None):
    final = final_url or url
    parent = _parent_url(final)

    def fake_get(u, timeout=12.0):
        if parent_html and parent and u.rstrip("/") == parent.rstrip("/"):
            return 200, parent, parent_html
        return 200, final, html

    with patch("ingest.live_status.HttpClient") as mock_client:
        mock_client.return_value.get.side_effect = fake_get
        return check_live_url(url=url, reference=REF, use_ai_fallback=False, program_title=title)


def test_batch2_uebs_parent_page_retry():
    form_html = """
    <html><body>
    Hier finden Sie alle Formulare und Vordrucke für ÜBS.
    Anträge und Formulare ÜBS — Download-Bereich.
    </body></html>
    """
    parent_html = """
    <html><body>
    Förderung von überbetrieblichen Berufsbildungsstätten (ÜBS).
    Was wird gefördert? Wer wird gefördert? Landeszuschuss bis 25 Prozent.
    </body></html>
    """
    url = "https://wm.baden-wuerttemberg.de/de/arbeit/ueberbetriebliche-berufsbildung-uebs/antraege-und-formulare-uebs/"
    result = _check(
        form_html,
        url=url,
        title="Bau und Modernisierung von überbetrieblichen Berufsbildungsstätten (ÜBS)",
        parent_html=parent_html,
    )
    assert result.status == "active"
    assert result.canonical_url is not None
    assert "ueberbetriebliche-berufsbildung-uebs" in result.canonical_url
    assert result.redirect_type == "parent_page"


def test_batch2_foerderzusage_active():
    html = """
    <html><body>
    Arbeit Inklusiv — Lohnkostenzuschüsse für Menschen mit Behinderung.
    Sie erhalten durch die langfristige Förderzusage von fünf Jahren Planungssicherheit.
    </body></html>
    """
    result = _check(html, url="https://www.ifd-bw.de/arbeitgeber/foerdermoeglichkeiten/", title="Arbeit Inklusiv")
    assert result.status == "active"


def test_batch2_ausfallbuergschaft_active():
    html = """
    <html><body>
    Bürgschaftsbank Saarland — Ausfallbürgschaften bis zu 80% für KMU im Saarland.
    </body></html>
    """
    result = _check(html, url="https://www.sikb.de/buergschaftsbank", title="Ausfallbürgschaften")
    assert result.status == "active"


def test_batch2_zuwendung_altenpflege_active():
    html = """
    <html><body>
    Finanzierung der Altenpflegehilfeausbildung.
    Zuwendungen für den theoretischen und praktischen Unterricht im Rahmen der Altenpflegeausbildung.
    </body></html>
    """
    result = _check(
        html,
        url="https://lasv.brandenburg.de/lasv/de/soziales/berufliche-bildung/finanzierung-der-altenpflegehilfeausbildung/",
        title="Ausbildung in der Altenpflege",
    )
    assert result.status == "active"


def test_should_try_parent_for_form_only_page():
    text = "Hier finden Sie alle Formulare und Vordrucke. Anträge und Formulare ÜBS."
    assert _should_try_parent(
        text=text,
        status="unknown",
        program_title="ÜBS Förderung",
        url="https://example.de/programm/antraege-und-formulare/",
    )


def test_parent_url_strips_last_segment():
    url = "https://wm.baden-wuerttemberg.de/de/arbeit/uebs/antraege-und-formulare-uebs/"
    parent = _parent_url(url)
    assert parent.endswith("/uebs/")
