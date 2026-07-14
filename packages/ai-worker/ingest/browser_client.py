"""Playwright tabanlı senkron fetch — JS-render sayfalar için HttpClient uyumlu istemci."""

from __future__ import annotations

import html as html_module
import logging

from urllib.parse import urlparse, urlunparse

from ingest.domain_rules import expand_url_variants, get_rule_for_url, host_of, is_suspicious_redirect
from ingest.pdf_text import is_pdf_url, pdf_bytes_to_html

logger = logging.getLogger(__name__)

# Bu host'larda goto sıkça ERR_CONNECTION_TIMED_OUT — kısa timeout + fail-fast
TIMEOUT_PRONE_HOSTS = frozenset(
    {
        "nbank.de",
        "aufbaubank.de",
        "bundeswirtschaftsministerium.de",
        "bmwk.de",
    }
)

STEALTH_ARGS = ["--disable-blink-features=AutomationControlled"]

REJECT_SELECTORS = [
    'button:has-text("Nur notwendige")',
    'button:has-text("Nur essenzielle")',
    'button:has-text("Essenzielle Cookies")',
    'button:has-text("Ablehnen")',
    'button:has-text("Alle ablehnen")',
    'button:has-text("Webanalyse ablehnen")',
    'button:has-text("Alles ablehnen")',
    'a:has-text("Nur notwendige")',
]

ACCEPT_SELECTORS = [
    'button:has-text("Akzeptieren")',
    'button:has-text("Alle akzeptieren")',
    'button:has-text("Alle Cookies akzeptieren")',
    'button:has-text("Zustimmen")',
    'button:has-text("Einverstanden")',
    "#cookie-accept",
    "#sliding-popup button",
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


def strip_url_fragment(url: str) -> str:
    """Hash (#...) sunucuya gitmez; Playwright'ta gereksiz ve SPA'da sorun çıkarabilir."""
    parsed = urlparse(url)
    if not parsed.fragment:
        return url
    return urlunparse(parsed._replace(fragment=""))


def _enrich_html_with_inner_text(page, html: str, *, force: bool = False) -> str:
    try:
        inner = page.evaluate("() => document.body?.innerText || ''")
    except Exception:
        return html
    inner = (inner or "").strip()
    if len(inner) < 80 and not force:
        return html
    # bb-h.de u.ä.: Readability/HTML kann Widget greifen — force immer innerText
    if force:
        if len(inner) < 80:
            return html
        return f"<html><body>{html_module.escape(inner)}</body></html>"
    if len(inner) < 300:
        return html
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
        self._host_timeout_fails: dict[str, int] = {}

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

    def _fetch_pdf(self, url: str, timeout: float) -> tuple[int, str, str] | None:
        """PDF URL veya Download-is-starting → metin HTML. Başarısızsa None."""
        if self._context is None:
            return None
        try:
            api = self._context.request
            resp = api.get(url, timeout=timeout * 1000, fail_on_status_code=False)
            status = resp.status
            body = resp.body()
            ctype = (resp.headers.get("content-type") or "").lower()
            if status >= 400 or not body:
                return status if status else 0, url, ""
            if "pdf" not in ctype and not is_pdf_url(url) and not body[:8].startswith(b"%PDF"):
                return None
            html = pdf_bytes_to_html(body, source_url=url)
            if not html:
                return 200, url, ""
            return 200, url, html
        except Exception as exc:
            logger.warning("PDF fetch failed (%s): %s", url, exc.__class__.__name__)
            return None

    def _fetch_once(self, page, url: str, timeout: float, *, original_url: str) -> tuple[int, str, str]:
        url = strip_url_fragment(url)
        original_url = strip_url_fragment(original_url)
        rule = get_rule_for_url(url) or get_rule_for_url(original_url)
        wait_until = rule.wait_until if rule else self._wait_until
        effective_timeout = timeout
        if rule and rule.fetch_timeout_sec:
            effective_timeout = max(timeout, rule.fetch_timeout_sec)
        host = host_of(url)
        if host in TIMEOUT_PRONE_HOSTS or any(
            host.endswith("." + h) for h in TIMEOUT_PRONE_HOSTS
        ):
            # Ağ bloğu: uzun beklemeyi kes
            effective_timeout = min(effective_timeout, 25.0)

        # PDF: Playwright sıkça "Download is starting" → doğrudan binary
        if is_pdf_url(url):
            pdf_result = self._fetch_pdf(url, effective_timeout)
            if pdf_result is not None:
                return pdf_result

        response = None
        try:
            response = page.goto(
                url, wait_until="domcontentloaded", timeout=effective_timeout * 1000
            )
        except Exception as exc:
            msg = str(exc)
            if "Download is starting" in msg or "download" in msg.lower():
                pdf_result = self._fetch_pdf(url, effective_timeout)
                if pdf_result is not None:
                    return pdf_result
            if "ERR_CONNECTION_TIMED_OUT" in msg or "Timeout" in msg:
                self._host_timeout_fails[host] = self._host_timeout_fails.get(host, 0) + 1
            if rule and rule.accept_partial_on_timeout:
                try:
                    html = page.content()
                    if html and len(html) > 800:
                        force_inner = bool(rule.use_inner_text_fallback)
                        html = _enrich_html_with_inner_text(page, html, force=force_inner)
                        return 200, page.url, html
                except Exception:
                    pass
            raise
        if wait_until == "networkidle":
            try:
                page.wait_for_load_state(
                    "networkidle", timeout=min(15000, effective_timeout * 1000)
                )
            except Exception:
                pass
        else:
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
        render_ms = self._render_wait_ms + (rule.extra_render_wait_ms if rule else 0)
        if render_ms:
            page.wait_for_timeout(render_ms)
        if self._dismiss_cookies:
            dismiss_consent(page)

        final_url = page.url
        if is_suspicious_redirect(original_url, final_url):
            logger.warning(
                "Suspicious redirect (possible hijack): %s → %s", original_url, final_url
            )
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

        url = strip_url_fragment(url)
        host = host_of(url)
        # Aynı host'ta peş peşe timeout → alternatif URL denemeyi atla
        if self._host_timeout_fails.get(host, 0) >= 2:
            logger.warning("Skipping %s — host already timed out %sx", host, self._host_timeout_fails[host])
            return 0, url, ""

        last_result = (0, url, "")
        for attempt_url in expand_url_variants(url):
            attempt_url = strip_url_fragment(attempt_url)
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
                    "Playwright fetch failed (%s): %s: %s",
                    attempt_url,
                    exc.__class__.__name__,
                    str(exc)[:160],
                )
                if self._host_timeout_fails.get(host, 0) >= 2:
                    break
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        return last_result
