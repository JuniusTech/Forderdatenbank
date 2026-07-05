"""Parser ve hash unit testleri — ağ gerektirmez."""

from ingest.hash_utils import compute_content_hash_from_html
from ingest.list_parser import parse_list_page, parse_total_hits
from ingest.pagination import get_next_page_url
from tests.fixtures.sample_pages import DETAIL_PAGE_FIXTURE, LIST_PAGE_FIXTURE

BASE = "https://www.foerderdatenbank.de"
LIST_URL = f"{BASE}/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html"


def test_parse_total_hits():
    assert parse_total_hits(LIST_PAGE_FIXTURE) == 2488


def test_parse_list_page():
    entries = parse_list_page(LIST_PAGE_FIXTURE, BASE, LIST_URL)
    assert len(entries) == 2
    assert entries[0].title == "Test Programm A"
    assert "Foerderprogramm/Bund" in entries[0].detail_url
    assert entries[0].target_group == "Kleine und mittlere Unternehmen"


def test_pagination():
    next_url = get_next_page_url(LIST_PAGE_FIXTURE, LIST_URL)
    assert next_url is not None
    assert "gtp=2" in next_url


def test_content_hash_stable():
    h1 = compute_content_hash_from_html(DETAIL_PAGE_FIXTURE)
    h2 = compute_content_hash_from_html(DETAIL_PAGE_FIXTURE)
    assert h1 == h2
    assert len(h1) == 64
