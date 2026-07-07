from unittest.mock import patch

from ai.page_extractor import PageExtractResult, extract_page_with_ai
from ingest.live_status import check_live_url


def test_ai_fallback_when_regex_unknown():
    html = "<html><body><p>Förderperiode 2023 bis 2027. Anträge über FIONA.</p></body></html>"
    fake_ai = PageExtractResult(
        status="active",
        reason="Laufende Förderperiode ohne abgelaufene Jahresfrist",
        funding_period="2023-2027",
        evidence_quote="Förderperiode 2023 bis 2027",
        confidence="medium",
        method="ollama",
    )

    with patch("ingest.live_status.HttpClient") as mock_client:
        mock_client.return_value.get.return_value = (200, "http://x", html)
        with patch("ai.page_extractor.extract_page_with_ai", return_value=fake_ai):
            result = check_live_url(
                "http://x",
                program_title="AUKM Test",
                use_ai_fallback=True,
            )

    assert result.method == "ollama"
    assert result.status == "active"
    assert result.funding_period == "2023-2027"


def test_extract_page_with_ai_prefers_ollama():
    fake = PageExtractResult(status="active", reason="ok", method="ollama")

    with patch("ai.page_extractor.extract_page_with_ollama", return_value=fake) as ollama:
        with patch("ai.page_extractor.extract_page_with_claude") as claude:
            result = extract_page_with_ai(
                page_text="Förderperiode 2023 bis 2027",
                program_title="Test",
                page_url="http://x",
            )

    assert result is fake
    ollama.assert_called_once()
    claude.assert_not_called()


def test_extract_page_with_ai_falls_back_to_claude():
    fake = PageExtractResult(status="unknown", reason="unklar", method="claude")

    with patch("ai.page_extractor.extract_page_with_ollama", return_value=None):
        with patch("ai.page_extractor.extract_page_with_claude", return_value=fake) as claude:
            result = extract_page_with_ai(
                page_text="unbekannt",
                program_title="Test",
                page_url="http://x",
            )

    assert result is fake
    claude.assert_called_once()
