"""Fixture modu — ağ olmadan DB pipeline doğrulama."""

from datetime import datetime, timezone

from db.config import BASE_URL
from db.models import RawPage
from db.session import get_session, init_db
from ingest.crawl_logger import CrawlLogger
from ingest.hash_utils import compute_content_hash_from_html
from tests.fixtures.sample_pages import DETAIL_PAGE_FIXTURE, LIST_PAGE_FIXTURE
from ingest.list_parser import parse_list_page


def run_fixture_crawl(mode: str = "fixture") -> None:
    init_db()
    base = BASE_URL
    list_url = f"{base}/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html"

    with get_session() as session:
        crawl_logger = CrawlLogger(session, mode=mode)
        entries = parse_list_page(LIST_PAGE_FIXTURE, base, list_url)
        crawl_logger.record_page_checked()
        crawl_logger.record_total_hits(2488)

        for entry in entries:
            url = entry.detail_url
            html = DETAIL_PAGE_FIXTURE.replace("Test Förderprogramm", entry.title)
            content_hash = compute_content_hash_from_html(html)
            now = datetime.now(timezone.utc)

            existing = session.get(RawPage, url)
            if existing is None:
                session.add(
                    RawPage(
                        url=url,
                        raw_html=html,
                        content_hash=content_hash,
                        first_seen_at=now,
                        last_synced_at=now,
                    )
                )
                crawl_logger.record_new()
            else:
                crawl_logger.record_skipped()

        crawl_logger.finish()
