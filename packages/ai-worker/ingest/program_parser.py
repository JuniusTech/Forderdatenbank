"""Tek bir Förderprogramm XML dosyasını yapılandırılmış kayda dönüştürür."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ingest.deadline_parser import scan_program_fields
from ingest.link_resolver import LinkResolver
from ingest.xml_utils import (
    build_raw_text,
    compute_program_hash,
    extract_classified_links,
    extract_date,
    extract_richtext,
    extract_string,
    find_property,
    parse_xml,
    region_from_program_path,
)

LICENSE_ATTRIBUTION = (
    "Quelle: Förderdatenbank des Bundes und der Länder "
    "(https://www.foerderdatenbank.de) — Lizenz: CC BY-ND 4.0 DE"
)

CLASSIFIER_FIELDS = {
    "Foerderart": "funding_type",
    "Foerderberechtigte": "target_groups",
    "Foerderbereich": "eligible_costs",
    "Unternehmensgroesse": "company_sizes",
}


@dataclass
class ParsedProgram:
    source_id: str
    source_path: str
    title: str
    funding_type: list[str] = field(default_factory=list)
    provider_name: str | None = None
    region: str = "unknown"
    target_groups: list[str] = field(default_factory=list)
    eligible_costs: list[str] = field(default_factory=list)
    company_sizes: list[str] = field(default_factory=list)
    external_links: list[dict[str, str]] = field(default_factory=list)
    application_url: str | None = None
    contact: dict | None = None
    raw_text: str = ""
    content_hash: str = ""
    date_of_issue: datetime | None = None
    status: str = "unknown"
    license_attribution: str = LICENSE_ATTRIBUTION

    def to_db_payload(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "title": self.title,
            "funding_type": self.funding_type,
            "provider_name": self.provider_name,
            "region": self.region,
            "target_groups": self.target_groups,
            "eligible_costs": self.eligible_costs,
            "company_sizes": self.company_sizes,
            "external_links": self.external_links,
            "application_url": self.application_url,
            "contact": self.contact,
            "raw_text": self.raw_text,
            "content_hash": self.content_hash,
            "date_of_issue": self.date_of_issue,
            "status": self.status,
            "license_attribution": self.license_attribution,
        }


def parse_program_file(path: Path, resolver: LinkResolver) -> ParsedProgram:
    root = parse_xml(path)
    source_id = root.get("name") or path.stem
    doc_path = root.get("path") or str(path.parent)
    source_path = f"{doc_path}/{source_id}"
    source_id = source_path

    title = extract_richtext(find_property(root, "gsb:title")) or source_id
    region = region_from_program_path(path)

    text_parts = {
        "summary": extract_richtext(find_property(root, "gsb:summary")),
        "bodyText": extract_richtext(find_property(root, "gsb:bodyText")),
        "regulatoryFWork": extract_richtext(find_property(root, "gsb:regulatoryFWork")),
        "procDescription": extract_richtext(find_property(root, "gsb:procDescription")),
        "procMethod": extract_richtext(find_property(root, "gsb:procMethod")),
        "procInfluence": extract_richtext(find_property(root, "gsb:procInfluence")),
    }
    frist_text = extract_richtext(find_property(root, "gsb:frist")) or (
        extract_string(find_property(root, "gsb:frist")) or ""
    )
    raw_text = build_raw_text(text_parts)
    date_of_issue = extract_date(find_property(root, "gsb:dateOfIssue"))

    classified = extract_classified_links(find_property(root, "gsb:cl2Processes"))
    funding_type: list[str] = []
    target_groups: list[str] = []
    eligible_costs: list[str] = []
    company_sizes: list[str] = []
    provider_name: str | None = None

    for classifier, hrefs in classified.items():
        labels = resolver.resolve_labels(hrefs)
        if classifier == "Foerderart":
            funding_type = labels
        elif classifier == "Foerderberechtigte":
            target_groups = labels
        elif classifier == "Foerderbereich":
            eligible_costs = labels
        elif classifier == "Unternehmensgroesse":
            company_sizes = labels
        elif classifier == "Foerdergebiet" and labels:
            region = labels[0]
        elif classifier == "Foerderorganisation" and hrefs:
            provider_name = resolver.resolve_provider_name(hrefs[0])

    contact_hrefs = []
    for hrefs in extract_classified_links(find_property(root, "gsb:cl2Contacts")).values():
        contact_hrefs.extend(hrefs)
    contact = resolver.resolve_contact(contact_hrefs[0]) if contact_hrefs else None

    external_hrefs = []
    for hrefs in extract_classified_links(find_property(root, "gsb:cl2CustServices")).values():
        external_hrefs.extend(hrefs)
    external_links = resolver.resolve_external_links(external_hrefs)
    application_url = external_links[0]["url"] if external_links else (contact or {}).get("website")

    status_result = scan_program_fields(
        {
            "frist": frist_text,
            "summary": text_parts["summary"],
            "bodyText": text_parts["bodyText"],
            "procDescription": text_parts["procDescription"],
            "procMethod": text_parts["procMethod"],
            "procInfluence": text_parts["procInfluence"],
            "regulatoryFWork": text_parts["regulatoryFWork"],
        }
    )

    program = ParsedProgram(
        source_id=source_id,
        source_path=source_path,
        title=title,
        funding_type=funding_type,
        provider_name=provider_name,
        region=region,
        target_groups=target_groups,
        eligible_costs=eligible_costs,
        company_sizes=company_sizes,
        external_links=external_links,
        application_url=application_url,
        contact=contact,
        raw_text=raw_text,
        date_of_issue=date_of_issue,
        status=status_result.status,
    )
    program.content_hash = compute_program_hash(program.to_db_payload())
    return program


def iter_program_files(export_root: Path) -> list[Path]:
    programs_dir = export_root / "FDB/Content/DE/Foerderprogramm"
    if not programs_dir.is_dir():
        raise FileNotFoundError(f"Program klasörü bulunamadı: {programs_dir}")
    return sorted(programs_dir.rglob("*.xml"))
