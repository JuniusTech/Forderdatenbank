"""Radware / bot protection detection."""

from bs4 import BeautifulSoup

CAPTCHA_MARKERS = (
    "radware captcha",
    "radware page",
    "captcha page",
    "bot manager",
    "access denied",
)


def is_blocked_page(html: str, title: str | None = None) -> bool:
    lower = html.lower()
    if any(marker in lower for marker in CAPTCHA_MARKERS):
        return True
    if title and any(marker in title.lower() for marker in CAPTCHA_MARKERS):
        return True
    # Gerçek liste sayfasında en az bir kart veya hit sayacı olmalı
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("div.search--hits") or soup.select_one("div.card--fundingprogram"):
        return False
    if len(html) < 5000 and "foerderprogramm" not in lower:
        return True
    return False
