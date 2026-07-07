"""Hard filter — deterministik eleme (AI yok)."""

from __future__ import annotations

from db.models import Company, FundingProgram

from matcher.rules import NATIONWIDE_REGIONS, _employees_to_size, _normalize

# Program target_groups bu terimlerden en az birini içermeli (KMU/gastronomi uyumu)
SME_TARGET_INDICATORS = {
    "unternehmen",
    "kmu",
    "kleine",
    "mittlere",
    "kleinst",
    "gründung",
    "existenzgründung",
    "privatperson",
    "freiberufler",
    "handwerk",
    "gewerbe",
}


def _region_passes(company_region: str, program_region: str | None) -> bool:
    company = _normalize(company_region)
    program = _normalize(program_region)
    if not program:
        return True
    if program in NATIONWIDE_REGIONS:
        return True
    return company in program or program in company


def _target_group_passes(company: Company, program: FundingProgram) -> bool:
    groups = program.target_groups or []
    if not groups:
        return True

    normalized = {_normalize(g) for g in groups}
    if normalized & SME_TARGET_INDICATORS:
        return True
    # Herhangi bir grup "unternehmen" benzeri içeriyorsa
    return any(any(ind in g for ind in SME_TARGET_INDICATORS) for g in normalized)


def _is_sme(company: Company) -> bool:
    size = _normalize(company.company_size) or _employees_to_size(company.employees)
    if size in {"klein", "mittel"}:
        return True
    if company.employees is not None and company.employees < 250:
        return True
    return False


def passes_hard_filter(company: Company, program: FundingProgram) -> tuple[bool, str]:
    if program.status == "closed":
        return False, "Programm geschlossen — keine Antragstellung"

    if not _region_passes(company.region, program.region):
        return False, f"Region passt nicht ({program.region})"

    if _is_sme(company) and not _target_group_passes(company, program):
        return False, "Zielgruppe nicht für KMU/Unternehmen"

    return True, "Hard filter bestanden"


def filter_programs(company: Company, programs: list[FundingProgram]) -> list[FundingProgram]:
    return [p for p in programs if passes_hard_filter(company, p)[0]]
