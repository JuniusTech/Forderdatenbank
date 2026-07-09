"""Playwright tabanlı senkron fetch — JS-render sayfalar için HttpClient uyumlu istemci."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

STEALTH_ARGS = ["--disable-blink-features=AutomationControlled"]

REJECT_SELECTORS = [
    'button:has-text("Nur notwendige")',
    'button:has-text("Ablehnen")',
    'button:has-text("Alle ablehnen")',
    'button:has-text("Webanalyse ablehnen")',
]

ACCEPT_SELECTORS = [
    'button:has-text("Akzeptieren")',
    'button:has-text("Alle akzeptieren")',
    'button:has-text("Zustimmen")',
    "#cookie-accept",
]

CAPTCHA_SELECTORS = [
    'iframe[src*="recaptcha"]',
    'iframe[src*="hcaptcha"]',
    ".g-recaptcha",
    'text=/Radware Captcha|hCaptcha|reCAPTCHA/i',
]


def dismiss_consent(page) -> bool:
    for sel in [*REJECT_SELECTORS, *ACCEPT_SELECTORS]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1200):
                btn.click(timeout=2000)
                page.wait_for_timeout(300)
                return True
        except Exception:
            continue
    return False


def detect_captcha(page) -> bool:
    for sel in CAPTCHA_SELECTORS:
        try:
            if page.locator(sel).first.is_visible(timeout=800):
                return True
        except Exception:
            continue
    return False


class PlaywrightClient:
    """Tek tarayıcı örneğini tüm istekler için yeniden kullanır. with-blok destekli."""

    def __init__(
        self,
        *,
        headless: bool = True,
        wait_until: str = "domcontentloaded",
        render_wait_ms: int = 1500,
        dismiss_cookies: bool = True,
    ) -> None:
        self._headless = headless
        self._wait_until = wait_until
        self._render_wait_ms = render_wait_ms
        self._dismiss_cookies = dismiss_cookies
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self) -> "PlaywrightClient":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless, args=STEALTH_ARGS)
        self._context = self._browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
            user_agent=(
                "FoerderdatenbankMonitor/1.0 (+https://github.com/local/foerderdatenbank; research bot)"
            ),
        )
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer:
                    closer.close()
            except Exception:
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._context = self._browser = self._pw = None

    def get(self, url: str, timeout: float = 60.0) -> tuple[int, str, str]:
        if self._context is None:
            raise RuntimeError("PlaywrightClient with-blok içinde kullanılmalı")

        page = self._context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        try:
            response = page.goto(url, wait_until=self._wait_until, timeout=timeout * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            if self._render_wait_ms:
                page.wait_for_timeout(self._render_wait_ms)
            if self._dismiss_cookies:
                dismiss_consent(page)
            if detect_captcha(page):
                logger.warning("CAPTCHA detected on %s", url)
                return 0, page.url, ""
            status = response.status if response else 0
            final_url = page.url
            html = page.content()
            return status, final_url, html
        except Exception as exc:
            logger.warning("Playwright fetch failed (%s): %s", url, exc.__class__.__name__)
            return 0, url, ""
        finally:
            try:
                page.close()
            except Exception:
                pass
