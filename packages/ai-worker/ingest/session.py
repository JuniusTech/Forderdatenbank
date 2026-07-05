from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


@asynccontextmanager
async def browser_session(headless: bool = True) -> AsyncGenerator[tuple[Browser, BrowserContext], None]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context(
            locale="de-DE",
            user_agent=(
                "CulinaryFundingOS/1.0 (research crawler; "
                "+https://github.com/juniustech; foerderdatenbank compliance)"
            ),
        )
        try:
            yield browser, context
        finally:
            await context.close()
            await browser.close()


async def new_page(context: BrowserContext) -> Page:
    return await context.new_page()
