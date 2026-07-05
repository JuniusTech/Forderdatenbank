import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

# Bot tespitini azaltmak için launch argümanları
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
]


@asynccontextmanager
async def browser_session(
    headless: bool = True,
    channel: str | None = None,
    cookies_file: str | None = None,
) -> AsyncGenerator[tuple[Browser, BrowserContext], None]:
    async with async_playwright() as playwright:
        launch_kwargs: dict = {
            "headless": headless,
            "args": STEALTH_ARGS,
        }
        if channel:
            launch_kwargs["channel"] = channel

        browser = await playwright.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 900},
        )

        if cookies_file:
            await _load_cookies(context, cookies_file)

        try:
            yield browser, context
        finally:
            await context.close()
            await browser.close()


async def _load_cookies(context: BrowserContext, cookies_file: str) -> None:
    path = Path(cookies_file)
    if not path.exists():
        raise FileNotFoundError(f"Cookie dosyası bulunamadı: {cookies_file}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    cookies = raw if isinstance(raw, list) else raw.get("cookies", raw)
    await context.add_cookies(cookies)


async def new_page(context: BrowserContext) -> Page:
    page = await context.new_page()
    # navigator.webdriver bayrağını gizle
    await page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    return page
