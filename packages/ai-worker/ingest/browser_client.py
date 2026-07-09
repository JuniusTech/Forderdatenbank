"""Playwright tabanlı senkron fetch — JS-render sayfalar için HttpClient uyumlu istemci."""

from __future__ import annotations

import html as html_module
import logging
from urllib.parse import urlparse, urlunparse

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


def _url_variants(url: str) -> list[str]:
    parsed = urlparse(url)
    variants = [url]
    if parsed.netloc == "lfa.de":
        variants.append(urlunparse(parsed._replace(netloc="www.lfa.de")))
    if parsed.netloc and not parsed.netloc.startswith("www."):
        variants.append(urlunparse(parsed._replace(netloc="www." + parsed.netloc)))
    # bmfsfj -> bmbfsfj.bund.de path preserve
    if "bmfsfj.de" in parsed.netloc:
        variants.append(
            url.replace("bmfsfj.de", "bmbfsfj.bund.de").replace("www.bmfsfj", "www.bmbfsfj")
        )
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _enrich_html_with_inner_text(page, html: str) -> str:
    try:
        inner = page.evaluate("() => document.body?.innerText || ''")
    except Exception:
        return html
    inner = (inner or "").strip()
    if len(inner) < 300:
        return html
    # SPA: innerText genelde soup'tan daha zengin (nbank, aufbaubank)
    if len(inner) > len(html) * 0.15:
        return f"<html><body>{html_module.escape(inner)}</body></html>"
    return html


class PlaywrightClient:
    """Tek tarayıcı örneğini tüm istekler için yeniden kullanır. with-blok destekli."""

    def __init__(
        self,
        *,
        headless: bool = True,
        wait_until: str = "domcontentloaded",
        render_wait_ms: int = 2000,
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

    def _fetch_once(self, page, url: str, timeout: float) -> tuple[int, str, str]:
        response = page.goto(url, wait_until=self._wait_until, timeout=timeout * 1000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
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
        html = _enrich_html_with_inner_text(page, page.content())
        return status, final_url, html

    def get(self, url: str, timeout: float = 60.0) -> tuple[int, str, str]:
        if self._context is None:
            raise RuntimeError("PlaywrightClient with-blok içinde kullanılmalı")

        last_result = (0, url, "")
        for attempt_url in _url_variants(url):
            page = self._context.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
            try:
                result = self._fetch_once(page, attempt_url, timeout)
                last_result = result
                status, final_url, html = result
                if status == 200 and html.strip():
                    return result
            except Exception as exc:
                logger.warning(
                    "Playwright fetch failed (%s): %s", attempt_url, exc.__class__.__name__
                )
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        return last_result
