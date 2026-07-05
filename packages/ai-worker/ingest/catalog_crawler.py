"""
Förderdatenbank catalog crawler — Faz 1 backfill / Faz 2 incremental.

Selector'lar docs/html-field-map.md'den; CMS değişirse crawl_runs.errors alarm üretir.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import Page

from db.config import CRAWL_DELAY_SECONDS, SEARCH_START_URL
from db.models import RawPage
from db.session import get_session, init_db
from ingest.captcha_detect import is_blocked_page
from ingest.crawl_logger import CrawlLogger
from ingest.detail_fetcher import fetch_detail_page
from ingest.list_parser import parse_list_page, parse_total_hits
from ingest.rate_limiter import RateLimiter
from ingest.selectors import LIST_REQUIRED_SELECTORS, PAGINATION_NEXT
from ingest.session import browser_session, new_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class BotBlockedError(RuntimeError):
    """Förderdatenbank Radware/bot koruması aktif."""


async def _assert_not_blocked(html: str, url: str, crawl_logger: CrawlLogger) -> None:
    from bs4 import BeautifulSoup

    title = BeautifulSoup(html, "html.parser").title
    title_text = title.get_text(strip=True) if title else None
    if is_blocked_page(html, title_text):
        err = {
            "url": url,
            "type": "bot_blocked",
            "title": title_text,
            "hint": (
                "Radware CAPTCHA aktif. --no-headless dene veya manuel tarayıcı oturumundan "
                "cookie aktar. Ağ testi: docs/data-sources.md#bot-schutz"
            ),
        }
        crawl_logger.record_error(err)
        raise BotBlockedError(err["hint"])


async def _check_list_selectors(page: Page, url: str, crawl_logger: CrawlLogger) -> None:
    for selector in LIST_REQUIRED_SELECTORS:
        if await page.locator(selector).count() == 0:
            crawl_logger.record_error(
                {"url": url, "selector": selector, "type": "selector_not_found"}
            )


async def _get_next_page_url(page: Page, current_url: str) -> str | None:
    next_link = page.locator(PAGINATION_NEXT)
    if await next_link.count() == 0:
        return None
    href = await next_link.first.get_attribute("href")
    if not href:
        return None
    return urljoin(current_url, href)


def _upsert_raw_page(session, url: str, html: str, content_hash: str) -> str:
    """Returns 'new', 'changed', or 'skipped'."""
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
        return "new"

    if existing.content_hash == content_hash:
        return "skipped"

    existing.raw_html = html
    existing.content_hash = content_hash
    existing.last_synced_at = now
    return "changed"


async def run_crawler(
    mode: str,
    max_list_pages: int | None = None,
    max_details: int | None = None,
    crawl_delay: float = CRAWL_DELAY_SECONDS,
    headless: bool = True,
    early_stop_after_empty_pages: int | None = None,
) -> None:
    init_db()

    with get_session() as session:
        crawl_logger = CrawlLogger(session, mode=mode)
        rate_limiter = RateLimiter(delay_seconds=crawl_delay)
        details_fetched = 0
        consecutive_empty_pages = 0
        list_page_num = 0

        async with browser_session(headless=headless) as (_, context):
            page = await new_page(context)

            # İlk liste sayfası — rate limit yok (oturum başlangıcı)
            logger.info("Opening search: %s", SEARCH_START_URL)
            await page.goto(SEARCH_START_URL, wait_until="domcontentloaded", timeout=60_000)
            current_url = page.url
            first_html = await page.content()
            await _assert_not_blocked(first_html, current_url, crawl_logger)

            while True:
                list_page_num += 1
                if max_list_pages and list_page_num > max_list_pages:
                    logger.info("Reached max_list_pages=%s", max_list_pages)
                    break

                html = await page.content()
                await _check_list_selectors(page, current_url, crawl_logger)

                total_hits = parse_total_hits(html)
                if total_hits is not None:
                    crawl_logger.record_total_hits(total_hits)
                    logger.info("List page %s — total hits: %s", list_page_num, total_hits)

                entries = parse_list_page(html, current_url, current_url)
                crawl_logger.record_page_checked()
                logger.info("List page %s — %s programs found", list_page_num, len(entries))

                page_had_updates = False

                for entry in entries:
                    if max_details and details_fetched >= max_details:
                        logger.info("Reached max_details=%s", max_details)
                        crawl_logger.finish()
                        return

                    existing = session.get(RawPage, entry.detail_url)

                    if mode == "incremental" and existing is not None:
                        # Detay çekmeden önce liste hash'i bilinmiyor; detay çekip karşılaştır
                        pass

                    result = await fetch_detail_page(page, entry.detail_url, rate_limiter)
                    details_fetched += 1

                    for err in result.errors:
                        crawl_logger.record_error(err)

                    if not result.html or not result.content_hash:
                        continue

                    action = _upsert_raw_page(
                        session, entry.detail_url, result.html, result.content_hash
                    )
                    session.flush()

                    if action == "new":
                        crawl_logger.record_new()
                        page_had_updates = True
                        logger.info("NEW: %s", entry.title[:80])
                    elif action == "changed":
                        crawl_logger.record_changed()
                        page_had_updates = True
                        logger.info("CHANGED: %s", entry.title[:80])
                    else:
                        crawl_logger.record_skipped()

                if early_stop_after_empty_pages is not None:
                    if page_had_updates:
                        consecutive_empty_pages = 0
                    else:
                        consecutive_empty_pages += 1
                        logger.info(
                            "No updates on page %s (%s/%s empty streak)",
                            list_page_num,
                            consecutive_empty_pages,
                            early_stop_after_empty_pages,
                        )
                        if consecutive_empty_pages >= early_stop_after_empty_pages:
                            crawl_logger.finish(stopped_early_at_page=list_page_num)
                            return

                next_url = await _get_next_page_url(page, current_url)
                if not next_url:
                    logger.info("No next page — crawl complete")
                    break

                await rate_limiter.wait()
                await page.goto(next_url, wait_until="domcontentloaded", timeout=60_000)
                current_url = page.url

        crawl_logger.finish()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Förderdatenbank catalog crawler")
    parser.add_argument(
        "--mode",
        choices=["backfill", "incremental", "smoke", "fixture"],
        default="backfill",
        help="backfill=full catalog; incremental=early stop; smoke=1 page; fixture=offline DB test",
    )
    parser.add_argument("--max-list-pages", type=int, default=None)
    parser.add_argument("--max-details", type=int, default=None)
    parser.add_argument(
        "--crawl-delay",
        type=float,
        default=CRAWL_DELAY_SECONDS,
        help="Seconds between requests (robots.txt default: 30)",
    )
    parser.add_argument("--no-headless", action="store_true")
    args = parser.parse_args(argv)

    if args.mode == "fixture":
        from ingest.fixture_crawler import run_fixture_crawl

        run_fixture_crawl()
        return 0

    max_list_pages = args.max_list_pages
    max_details = args.max_details
    early_stop = None

    if args.mode == "smoke":
        max_list_pages = max_list_pages or 1
        max_details = max_details or 10
        if args.crawl_delay == CRAWL_DELAY_SECONDS:
            args.crawl_delay = 2.0  # smoke test için kısa delay
    elif args.mode == "incremental":
        early_stop = 3

    try:
        asyncio.run(
            run_crawler(
                mode=args.mode,
                max_list_pages=max_list_pages,
                max_details=max_details,
                crawl_delay=args.crawl_delay,
                headless=not args.no_headless,
                early_stop_after_empty_pages=early_stop,
            )
        )
    except BotBlockedError as exc:
        logger.error("Bot protection: %s", exc)
        return 2
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
