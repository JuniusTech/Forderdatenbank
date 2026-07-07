"""AI başvuru taslağı üretici — Claude API veya template fallback."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from db.models import Company, FundingProgram, Match

PROMPT_PATH = Path(__file__).parent / "prompts" / "system_de.txt"
DRAFT_STAMP = "ENTWURF"


def _template_draft(company: Company, program: FundingProgram, match: Match | None) -> dict[str, Any]:
    need = company.investment_need or "[BERATER AUSFÜLLEN: Investitionsbedarf]"
    sector = company.sector or "[BERATER AUSFÜLLEN: Branche]"
    employees = company.employees or "[BERATER AUSFÜLLEN: Mitarbeiterzahl]"

    application_text = f"""ENTWURF — Antragstext (unverbindlich)

Sehr geehrte Damen und Herren,

hiermit beantragt {company.name} ({company.region}) eine Förderung im Rahmen des Programms „{program.title}“.

Unternehmensprofil:
- Branche: {sector}
- Mitarbeitende: {employees}
- Geplanter Investitionsbedarf: {need}

Projektziel:
Wir planen Investitionen zur Stärkung unserer Wettbewerbsfähigkeit im Bereich {sector}. 
Der Schwerpunkt liegt auf: {need}.

[BERICHT AUSFÜLLEN: Konkrete Maßnahmen, Zeitplan, erwartete Wirkungen]

Förderrelevante Angaben stützen wir auf die Programmbeschreibung der Förderdatenbank.
Maßgeblich sind die Angaben auf den offiziellen Webseiten der fördergebenden Stelle.

Mit freundlichen Grüßen
{company.name}
"""

    return {
        "status": DRAFT_STAMP,
        "project_title": f"Investitionsvorhaben {company.name}",
        "project_summary": (
            f"{company.name} ({company.region}) plant Investitionen im Bereich {need}. "
            f"Zielprogramm: {program.title}."
        ),
        "investment_plan": [
            {
                "item": "Investitionsmaßnahme 1",
                "description": need,
                "amount_placeholder": "[BERATER AUSFÜLLEN: Betrag in EUR]",
            }
        ],
        "expected_effects": {
            "digitalization": "[BERATER AUSFÜLLEN]" if "digital" not in need.lower() else need,
            "sustainability": "[BERATER AUSFÜLLEN]",
            "jobs": f"Aktuell {employees} Beschäftigte",
        },
        "application_text_de": application_text,
        "missing_fields": [
            "Detaillierter Kostenplan",
            "Zeitplan Meilensteine",
            "Anlagen/Nachweise",
        ],
        "disclaimer": (
            "Dieser Entwurf ist unverbindlich, keine Förderzusage. "
            "Beraterprüfung erforderlich. Endgültige Entscheidung bei der Förderstelle."
        ),
        "match_score": float(match.score) if match else None,
        "program_title": program.title,
        "generated_by": "template",
    }


def _parse_llm_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text)
    data["status"] = DRAFT_STAMP
    data["generated_by"] = "claude"
    return data


def _claude_draft(company: Company, program: FundingProgram, match: Match | None) -> dict[str, Any]:
    import anthropic

    system = PROMPT_PATH.read_text(encoding="utf-8")
    user_payload = {
        "company": {
            "name": company.name,
            "region": company.region,
            "sector": company.sector,
            "employees": company.employees,
            "investment_need": company.investment_need,
            "notes": company.notes,
        },
        "program": {
            "title": program.title,
            "region": program.region,
            "funding_type": program.funding_type,
            "provider": program.provider_name,
            "raw_excerpt": (program.raw_text or "")[:3500],
        },
        "match_score": float(match.score) if match else None,
        "matched_terms": match.matched_terms if match else [],
    }

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=2500,
        system=system,
        messages=[
            {
                "role": "user",
                "content": f"Erstelle den Antragsentwurf als JSON.\n\n{json.dumps(user_payload, ensure_ascii=False)}",
            }
        ],
    )
    raw = message.content[0].text
    return _parse_llm_json(raw)


def generate_draft(
    company: Company,
    program: FundingProgram,
    match: Match | None = None,
) -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            return _claude_draft(company, program, match)
        except Exception:
            pass
    return _template_draft(company, program, match)
