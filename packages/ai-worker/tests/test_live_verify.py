from unittest.mock import patch

from db.models import FundingProgram
from ingest.live_status import LiveStatusResult
from matcher.live_verify import clear_live_cache, needs_live_check, verify_match_results
from matcher.pipeline import MatchResult


def _program(**kw) -> FundingProgram:
    p = FundingProgram(
        source_id="test/p",
        source_path="/test/p",
        title=kw.get("title", "Test"),
        raw_text="x",
        content_hash="h",
        license_attribution="test",
        application_url=kw.get("application_url"),
        status=kw.get("status", "unknown"),
    )
    return p


def test_needs_live_check_only_unknown():
    assert needs_live_check("unknown") is True
    assert needs_live_check("active") is False
    assert needs_live_check("closed") is False
    assert needs_live_check("laufend") is False


def test_known_status_skips_http():
    clear_live_cache()
    prog = _program(application_url="https://example.com/p", status="closed")
    match = MatchResult(program=prog, score=80.0, breakdown={}, matched_terms=[], estimated_amount_range=None)
    with patch("matcher.live_verify._cached_check") as mock_check:
        outcomes = verify_match_results([match])
    mock_check.assert_not_called()
    assert outcomes[0].included is False
    assert outcomes[0].live_check["skipped"] is True


def test_unknown_live_closed_excludes_match():
    clear_live_cache()
    prog = _program(application_url="https://example.com/p", status="unknown")
    match = MatchResult(program=prog, score=80.0, breakdown={}, matched_terms=[], estimated_amount_range=None)
    closed = LiveStatusResult(
        url=prog.application_url,
        http_status=200,
        final_url=prog.application_url,
        status="closed",
        reason="Live-Seite: Keine Antragstellung möglich",
        snippet="seit dem 19.12.2023",
    )
    with patch("matcher.live_verify._cached_check", return_value=(closed, False)):
        outcomes = verify_match_results([match])
    assert len(outcomes) == 1
    assert outcomes[0].included is False
    assert outcomes[0].live_check["status"] == "closed"
    assert outcomes[0].live_check.get("skipped") is not True


def test_unknown_live_unreachable_still_included():
    clear_live_cache()
    prog = _program(application_url="https://example.com/p2", status="unknown")
    match = MatchResult(program=prog, score=70.0, breakdown={}, matched_terms=[], estimated_amount_range=None)
    unknown = LiveStatusResult(
        url=prog.application_url,
        http_status=0,
        final_url=prog.application_url,
        status="unknown",
        reason="Seite nicht erreichbar: Timeout",
    )
    with patch("matcher.live_verify._cached_check", return_value=(unknown, False)):
        outcomes = verify_match_results([match])
    assert outcomes[0].included is True
