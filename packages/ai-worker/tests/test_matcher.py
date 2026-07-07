"""Matcher pipeline testleri."""

from unittest.mock import MagicMock

from matcher.hard_filter import passes_hard_filter
from matcher.keyword_score import keyword_score
from matcher.pipeline import match_company_to_programs


def _company(**kwargs):
    c = MagicMock()
    c.name = kwargs.get("name", "Test GmbH")
    c.region = kwargs.get("region", "Berlin")
    c.sector = kwargs.get("sector", "Gastronomie")
    c.employees = kwargs.get("employees", 8)
    c.company_size = kwargs.get("company_size", "klein")
    c.investment_need = kwargs.get("investment_need", "Digitalisierung POS Energie")
    c.notes = kwargs.get("notes", None)
    return c


def _program(**kwargs):
    p = MagicMock()
    p.status = "active"
    p.title = kwargs.get("title", "Digitalbonus Berlin")
    p.region = kwargs.get("region", "Berlin")
    p.raw_text = kwargs.get("raw_text", "Digitalisierung und Energieeffizienz für Unternehmen")
    p.funding_type = kwargs.get("funding_type", ["Zuschuss"])
    p.target_groups = kwargs.get("target_groups", ["Unternehmen"])
    p.eligible_costs = kwargs.get("eligible_costs", [])
    p.company_sizes = kwargs.get("company_sizes", [])
    return p


def test_hard_filter_region_fail():
    ok, _ = passes_hard_filter(_company(region="Berlin"), _program(region="Bayern"))
    assert not ok


def test_hard_filter_region_pass_bundesweit():
    ok, _ = passes_hard_filter(_company(), _program(region="bundesweit"))
    assert ok


def test_keyword_score_finds_terms():
    score, breakdown, terms = keyword_score(_company(), _program())
    assert score > 0
    assert terms
    assert "total" in breakdown


def test_pipeline_limits_to_eight():
    company = _company()
    programs = [_program(title=f"P{i}", region="Berlin") for i in range(20)]
    results = match_company_to_programs(company, programs, min_score=1, limit=8)
    assert len(results) <= 8
