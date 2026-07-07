"""Deadline parser ve status çözümleme testleri."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ingest.deadline_parser import scan_program_fields, scan_text_field
from ingest.link_resolver import LinkResolver
from ingest.program_parser import parse_program_file

BMWI = Path(__file__).resolve().parents[3] / "BMWI"
REF = date(2026, 7, 7)


def test_effiziente_gebaeudeplus_closed():
    path = BMWI / "FDB/Content/DE/Foerderprogramm/Land/Berlin/effiziente-gebaeude-plus.xml"
    parsed = parse_program_file(path, LinkResolver(BMWI))
    assert parsed.status == "closed"


def test_palu_modul4_active_future_window():
    path = BMWI / "FDB/Content/DE/Foerderprogramm/Bund/BMU/palu-modul4-massnahmen-wiedervernaessung.xml"
    parsed = parse_program_file(path, LinkResolver(BMWI))
    assert parsed.status == "active"
    result = scan_program_fields(
        {
            "procInfluence": Path(path).read_text(encoding="utf-8"),
        },
        reference=REF,
    )
    # procInfluence penceresi gelecekte
    fields = {
        "summary": "",
        "bodyText": "",
        "procDescription": "",
        "procMethod": "",
        "procInfluence": "",
        "regulatoryFWork": "",
        "frist": "",
    }
    from ingest.xml_utils import find_property, extract_richtext, parse_xml

    root = parse_xml(path)
    for key, prop in [
        ("summary", "gsb:summary"),
        ("bodyText", "gsb:bodyText"),
        ("procInfluence", "gsb:procInfluence"),
        ("regulatoryFWork", "gsb:regulatoryFWork"),
    ]:
        fields[key] = extract_richtext(find_property(root, prop))
    status = scan_program_fields(fields, reference=REF)
    assert status.status == "active"
    assert status.application_end == date(2027, 1, 29)


def test_summary_alone_does_not_keep_open_when_body_has_past_deadline():
    fields = {
        "summary": "Reichen Sie bitte Ihren Antrag bei der IBB ein.",
        "bodyText": (
            "10 Geltungsdauer Die Förderrichtlinie gilt für alle Anträge, "
            "die bis zum 31. Dezember 2024 bei der Investitionsbank Berlin eingehen."
        ),
        "procDescription": "",
        "procMethod": "",
        "procInfluence": "",
        "regulatoryFWork": "",
        "frist": "",
    }
    result = scan_program_fields(fields, reference=REF)
    assert result.status == "closed"


def test_closed_keyword_forces_closed():
    text = "Seit dem 19.12.2023 ist keine Antragstellung für das Programm möglich."
    signals = scan_text_field(text, "summary")
    result = scan_program_fields({"summary": text}, reference=REF)
    assert any(s.kind == "closed_keyword" for s in signals)
    assert result.status == "closed"


def test_skip_zweckbindungsfrist_not_application_end():
    text = "Die Anlagen müssen bis zum Ende der Zweckbindungsfrist betrieben werden."
    result = scan_program_fields({"bodyText": text}, reference=REF)
    assert result.status == "unknown"
