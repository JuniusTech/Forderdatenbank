"""Keyword skoru + matched_terms — Faz2-3 C1."""

from __future__ import annotations

import re

from db.models import Company, FundingProgram

from matcher.rules import _normalize

# Firma ihtiyaç / sektör terimleri → program metninde aranır
DEFAULT_NEED_TERMS = [
    "digitalisierung",
    "digital",
    "pos",
    "kasse",
    "kassensystem",
    "webshop",
    "energie",
    "energieeffizienz",
    "investition",
    "modernisierung",
    "küche",
    "ausstattung",
    "filiale",
    "innovation",
    "forschung",
    "nachhaltigkeit",
    "gastronomie",
    "restaurant",
    "hotellerie",
    "lebensmittel",
]

FUNDING_TYPE_BONUS = {"zuschuss": 10, "darlehen": 5, "beteiligung": 3}
REGION_EXACT_BONUS = 15
REGION_NATIONWIDE_BONUS = 8


def _extract_terms(company: Company) -> list[str]:
    parts = [company.investment_need or "", company.sector or "", company.notes or ""]
    raw = " ".join(parts).lower()
    tokens = re.findall(r"[a-zäöüß]{4,}", raw, re.IGNORECASE)
    seen: set[str] = set()
    terms: list[str] = []
    for t in DEFAULT_NEED_TERMS + tokens:
        n = _normalize(t)
        if n and n not in seen:
            seen.add(n)
            terms.append(n)
    return terms[:30]


def _program_haystack(program: FundingProgram) -> str:
    return " ".join(
        [
            _normalize(program.title),
            _normalize(program.raw_text[:3000]),
            " ".join(_normalize(x) for x in program.eligible_costs),
            " ".join(_normalize(x) for x in program.funding_type),
            " ".join(_normalize(x) for x in program.target_groups),
        ]
    )


def keyword_score(
    company: Company,
    program: FundingProgram,
) -> tuple[float, dict, list[str]]:
    haystack = _program_haystack(program)
    terms = _extract_terms(company)
    matched: list[str] = []
    term_score = 0.0

    for term in terms:
        if term in haystack:
            matched.append(term)
            # Uzun terimler daha spesifik
            term_score += min(12, 4 + len(term) // 3)

    term_score = min(term_score, 55)

    breakdown: dict = {
        "keyword_hits": {
            "ok": bool(matched),
            "detail": ", ".join(matched[:8]) if matched else "Keine direkten Keyword-Treffer",
            "weight": round(term_score, 1),
        }
    }

    # funding_type — Zuschuss bonus wenn Firma Investitionsbedarf hat
    ft_bonus = 0.0
    if company.investment_need and program.funding_type:
        for ft in program.funding_type:
            key = _normalize(ft)
            for k, bonus in FUNDING_TYPE_BONUS.items():
                if k in key:
                    ft_bonus = max(ft_bonus, bonus)
    if ft_bonus:
        breakdown["funding_type"] = {
            "ok": True,
            "detail": f"Förderart passt (+{ft_bonus})",
            "weight": ft_bonus,
        }

    # region bonus
    region_bonus = 0.0
    company_r = _normalize(company.region)
    program_r = _normalize(program.region)
    if program_r in {"bundesweit", "bund", "eu", "deutschland"}:
        region_bonus = REGION_NATIONWIDE_BONUS
        breakdown["region_bonus"] = {
            "ok": True,
            "detail": f"Bundesweit/EU ({program.region})",
            "weight": region_bonus,
        }
    elif company_r and program_r and (company_r in program_r or program_r in company_r):
        region_bonus = REGION_EXACT_BONUS
        breakdown["region_bonus"] = {
            "ok": True,
            "detail": f"Landesprogramm ({program.region})",
            "weight": region_bonus,
        }

    total = min(100.0, term_score + ft_bonus + region_bonus)
    breakdown["total"] = round(total, 2)
    return round(total, 2), breakdown, matched


def estimate_amount_range(program: FundingProgram) -> str | None:
    """XML'de tutar yok — metinden EUR pattern dene, yoksa None."""
    text = program.raw_text or ""
    patterns = [
        r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(?:€|EUR|Euro)",
        r"bis zu\s+(\d{1,3}(?:\.\d{3})*)",
        r"maximal\s+(\d{1,3}(?:\.\d{3})*)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return f"bis ca. {m.group(1)} € (aus Programmtext)"
    return None
