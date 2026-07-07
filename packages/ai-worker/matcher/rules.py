"""Kural tabanlı program eşleştirme — MVP demo (AI yok)."""

from __future__ import annotations

from dataclasses import dataclass

from db.models import Company, FundingProgram

DISCLAIMER = (
    "Dies ist eine unverbindliche Vorauswahl. "
    "Die endgültige Entscheidung liegt bei der zuständigen Förderstelle."
)

NATIONWIDE_REGIONS = {"bundesweit", "bund", "deutschland", "eu"}

SIZE_ALIASES: dict[str, set[str]] = {
    "klein": {"kleines unternehmen", "kleinstunternehmen", "kleines_unternehmen", "kleinstunternehmen"},
    "mittel": {"mittleres unternehmen", "mittleres_unternehmen", "kmu"},
    "gross": {"großes unternehmen", "grosses unternehmen", "grosses_unternehmen"},
}


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _employees_to_size(employees: int | None) -> str | None:
    if employees is None:
        return None
    if employees < 10:
        return "klein"
    if employees < 250:
        return "mittel"
    return "gross"


def _region_match(company_region: str, program_region: str | None) -> tuple[bool, str]:
    company = _normalize(company_region)
    program = _normalize(program_region)
    if not program:
        return True, "Keine Regionsangabe im Programm"
    if program in NATIONWIDE_REGIONS or program == "bund":
        return True, f"Bundesweit/EU ({program_region})"
    if company in program or program in company:
        return True, f"Region passt ({program_region})"
    return False, f"Region passt nicht ({program_region})"


def _size_match(company: Company, program: FundingProgram) -> tuple[bool, str]:
    sizes = {_normalize(s) for s in (program.company_sizes or [])}
    if not sizes:
        return True, "Keine Größenvorgabe"

    profile_size = _normalize(company.company_size) or _employees_to_size(company.employees)
    if not profile_size:
        return True, "Keine Unternehmensgröße im Profil — weich bewertet"

    aliases = SIZE_ALIASES.get(profile_size, {profile_size})
    if sizes & aliases:
        return True, f"Unternehmensgröße passt ({profile_size})"
  # partial: KMU often listed
    if profile_size in {"klein", "mittel"} and any("kmu" in s or "klein" in s or "mittel" in s for s in sizes):
        return True, "KMU-relevante Größenkategorie"
    return False, f"Größe passt nicht ({', '.join(program.company_sizes[:3])})"


def _sector_match(company: Company, program: FundingProgram) -> tuple[bool, str]:
    sector = _normalize(company.sector)
    if not sector:
        return True, "Kein Sektor im Profil"

    haystack = " ".join(
        [
            _normalize(program.title),
            _normalize(program.raw_text[:2000]),
            " ".join(_normalize(x) for x in program.eligible_costs),
            " ".join(_normalize(x) for x in program.target_groups),
        ]
    )
    tokens = [t for t in sector.replace("/", " ").replace(",", " ").split() if len(t) > 3]
    hits = [t for t in tokens if t in haystack]
    if hits:
        return True, f"Sektor-Bezug: {', '.join(hits[:3])}"
    return False, "Kein direkter Sektor-Bezug"


def _investment_match(company: Company, program: FundingProgram) -> tuple[bool, str]:
    need = _normalize(company.investment_need)
    if not need:
        return True, "Kein Investitionsbedarf angegeben"

    haystack = " ".join(
        [
            _normalize(program.title),
            _normalize(program.raw_text[:1500]),
            " ".join(_normalize(x) for x in program.eligible_costs),
            " ".join(_normalize(x) for x in program.funding_type),
        ]
    )
    tokens = [t for t in need.replace("/", " ").split() if len(t) > 4]
    hits = [t for t in tokens if t in haystack]
    if hits:
        return True, f"Investitionsbezug: {', '.join(hits[:2])}"
    return False, "Kein Investitionsbezug"


@dataclass
class MatchResult:
    program: FundingProgram
    score: float
    breakdown: dict[str, str | bool | float]


def score_program(company: Company, program: FundingProgram) -> MatchResult | None:
    if program.status != "active":
        return None

    checks = [
        ("region", _region_match(company.region, program.region), 30),
        ("company_size", _size_match(company, program), 25),
        ("sector", _sector_match(company, program), 25),
        ("investment", _investment_match(company, program), 20),
    ]

    breakdown: dict[str, str | bool | float] = {}
    score = 0.0
    hard_fail = False

    for key, (ok, detail), weight in checks:
        breakdown[key] = {"ok": ok, "detail": detail, "weight": weight}
        if ok:
            score += weight
        elif key == "region":
            hard_fail = True

    if hard_fail:
        return None

    breakdown["total"] = round(score, 2)
    return MatchResult(program=program, score=round(score, 2), breakdown=breakdown)


def match_company_to_programs(
    company: Company,
    programs: list[FundingProgram],
    *,
    min_score: float = 40.0,
    limit: int = 25,
) -> list[MatchResult]:
    results: list[MatchResult] = []
    for program in programs:
        result = score_program(company, program)
        if result and result.score >= min_score:
            results.append(result)
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
