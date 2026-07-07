"""XML parser ve link resolver unit testleri — DB gerektirmez."""

from pathlib import Path

from ingest.link_resolver import LinkResolver
from ingest.program_parser import parse_program_file
from ingest.xml_utils import extract_richtext, find_property, parse_xml, region_from_program_path

_REPO_ROOT = Path(__file__).resolve().parents[3]
EXPORT_ROOT = _REPO_ROOT / "BMWI"
SAMPLE_PROGRAM = (
    EXPORT_ROOT
    / "FDB/Content/DE/Foerderprogramm/Bund/BMU/palu-modul4-massnahmen-wiedervernaessung.xml"
)


def test_region_from_program_path():
    path = Path("BMWI/FDB/Content/DE/Foerderprogramm/Land/Thueringen/foo.xml")
    assert region_from_program_path(path) == "Thueringen"
    path = Path("BMWI/FDB/Content/DE/Foerderprogramm/Bund/BMU/foo.xml")
    assert region_from_program_path(path) == "Bund"


def test_extract_richtext_from_sample():
    if not SAMPLE_PROGRAM.is_file():
        return
    root = parse_xml(SAMPLE_PROGRAM)
    title = extract_richtext(find_property(root, "gsb:title"))
    assert "Wiedervernässung" in title or "Palu" in title


def test_link_resolver_category_label():
    if not EXPORT_ROOT.is_dir():
        return
    resolver = LinkResolver(EXPORT_ROOT)
    label = resolver.resolve_label("target:/BMWI/SiteGlobals/Categories/FDB/Foerderart/zuschuss")
    assert label == "Zuschuss"


def test_parse_sample_program():
    if not SAMPLE_PROGRAM.is_file():
        return
    resolver = LinkResolver(EXPORT_ROOT)
    program = parse_program_file(SAMPLE_PROGRAM, resolver)
    assert program.source_id.endswith("palu-modul4-massnahmen-wiedervernaessung")
    assert program.title
    assert "Zuschuss" in program.funding_type
    assert program.contact is not None
    assert program.contact.get("email") == "office@rentenbank.de"
    assert program.application_url
    assert program.application_url.startswith("http")
    assert program.content_hash
    assert len(program.raw_text) > 100
