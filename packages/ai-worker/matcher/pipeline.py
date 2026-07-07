"""Eşleştirme pipeline: hard filter → keyword score."""

from __future__ import annotations

from dataclasses import dataclass

from db.models import Company, FundingProgram

from matcher.hard_filter import filter_programs, passes_hard_filter
from matcher.keyword_score import estimate_amount_range, keyword_score

DISCLAIMER = (
    "Dies ist eine unverbindliche Vorauswahl — Beraterprüfung erforderlich. "
    "Die endgültige Entscheidung liegt bei der zuständigen Förderstelle."
)


@dataclass
class MatchResult:
    program: FundingProgram
    score: float
    breakdown: dict
    matched_terms: list[str]
    estimated_amount_range: str | None


def match_company_to_programs(
    company: Company,
    programs: list[FundingProgram],
    *,
    min_score: float = 35.0,
    limit: int = 8,
) -> list[MatchResult]:
    pool = filter_programs(company, programs)
    results: list[MatchResult] = []

    for program in pool:
        ok, filter_reason = passes_hard_filter(company, program)
        if not ok:
            continue
        score, breakdown, matched_terms = keyword_score(company, program)
        breakdown["hard_filter"] = {"ok": True, "detail": filter_reason, "weight": 0}
        if score < min_score:
            continue
        results.append(
            MatchResult(
                program=program,
                score=score,
                breakdown=breakdown,
                matched_terms=matched_terms,
                estimated_amount_range=estimate_amount_range(program),
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
