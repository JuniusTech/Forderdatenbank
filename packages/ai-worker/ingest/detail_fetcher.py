import asyncio
from dataclasses import dataclass, field

from playwright.async_api import Page

from ingest.hash_utils import compute_content_hash_from_html, extract_hash_blocks
from ingest.rate_limiter import RateLimiter
from ingest.selectors import DETAIL_REQUIRED_SELECTORS


@dataclass
class DetailFetchResult:
    url: str
    html: str
    content_hash: str
    title: str
    errors: list[dict] = field(default_factory=list)


async def fetch_detail_page(
    page: Page,
    url: str,
    rate_limiter: RateLimiter,
) -> DetailFetchResult:
    await rate_limiter.wait()
    response = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)

    if response is None or not response.ok:
        status = response.status if response else "no response"
        return DetailFetchResult(
            url=url,
            html="",
            content_hash="",
            title="",
            errors=[{"url": url, "type": "http_error", "status": status}],
        )

    html = await page.content()
    errors: list[dict] = []

    for selector in DETAIL_REQUIRED_SELECTORS:
        if await page.locator(selector).count() == 0:
            errors.append({"url": url, "selector": selector, "type": "selector_not_found"})

    title = ""
    title_loc = page.locator("h1.title")
    if await title_loc.count() > 0:
        title = (await title_loc.first.inner_text()).strip()

    blocks = extract_hash_blocks(html)
    content_hash = compute_content_hash_from_html(html)

    if not any(blocks):
        errors.append({"url": url, "type": "empty_content_blocks"})

    return DetailFetchResult(
        url=url,
        html=html,
        content_hash=content_hash,
        title=title,
        errors=errors,
    )
