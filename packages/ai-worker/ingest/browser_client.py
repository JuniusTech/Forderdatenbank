"""Playwright tabanlı senkron fetch — JS-render sayfalar için HttpClient uyumlu istemci."""

from __future__ import annotations

import html as html_module
import logging

from ingest.domain_rules import expand_url_variants, get_rule_for_url, is_suspicious_redirect

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


def _enrich_html_with_inner_text(page, html: str, *, force: bool = False) -> str:
    try:
        inner = page.evaluate("() => document.body?.innerText || ''")
    except Exception:
        return html
    inner = (inner or "").strip()
    if len(inner) < 300:
        return html
    if force or len(inner) > len(html) * 0.15:
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
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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

    def _fetch_once(self, page, url: str, timeout: float, *, original_url: str) -> tuple[int, str, str]:
        rule = get_rule_for_url(url) or get_rule_for_url(original_url)
        wait_until = rule.wait_until if rule else self._wait_until
        # networkidle bazı sitelerde asla bitmez — timeout ile sınırla
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        except Exception:
            raise
        if wait_until == "networkidle":
            try:
                page.wait_for_load_state("networkidle", timeout=min(12000, timeout * 1000))
            except Exception:
                pass
        else:
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
        if self._render_wait_ms:
            page.wait_for_timeout(self._render_wait_ms)
        if self._dismiss_cookies:
            dismiss_consent(page)

        final_url = page.url
        if is_suspicious_redirect(original_url, final_url):
            logger.warning(
                "Suspicious redirect (possible hijack): %s → %s", original_url, final_url
            )
            # İçerik okuma / cookie yok — güvenli çık
            return 0, final_url, ""

        if detect_captcha(page):
            logger.warning("CAPTCHA detected on %s", url)
            return 0, final_url, ""

        status = response.status if response else 0
        force_inner = bool(rule and rule.use_inner_text_fallback)
        html = _enrich_html_with_inner_text(page, page.content(), force=force_inner)
        return status, final_url, html

    def get(self, url: str, timeout: float = 60.0) -> tuple[int, str, str]:
        if self._context is None:
            raise RuntimeError("PlaywrightClient with-blok içinde kullanılmalı")

        last_result = (0, url, "")
        for attempt_url in expand_url_variants(url):
            page = self._context.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
            try:
                result = self._fetch_once(page, attempt_url, timeout, original_url=url)
                last_result = result
                status, final_url, html = result
                if status == 0 and final_url and is_suspicious_redirect(url, final_url):
                    # Hijack — daha fazla deneme yapma
                    return result
                if status == 200 and html.strip():
                    return result
                # 404 ise lowercase/alt path zaten expand_url_variants içinde
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
