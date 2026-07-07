from ingest.live_status import html_to_text, scan_live_text

IBB_SNIPPET = """
Keine Antragstellung möglich
Sehr geehrte Damen und Herren, seit dem 19.12.2023 ist keine Antragstellung
für das Förderprogramm Effiziente GebäudePLUS möglich.
"""


def test_ibb_live_closed():
    status, reason, closure, _ = scan_live_text(IBB_SNIPPET)
    assert status == "closed"
    assert closure is not None
    assert closure.year == 2023 and closure.month == 12 and closure.day == 19


def test_html_to_text_strips_tags():
    text = html_to_text("<p>Keine <strong>Antragstellung</strong> möglich</p>")
    assert "Keine Antragstellung möglich" in text
