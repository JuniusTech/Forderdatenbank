from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ingest.selectors import PAGINATION_NEXT


def get_next_page_url(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    # Önce "weiter" linki
    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(strip=True).lower()
        if text == "weiter":
            return urljoin(current_url, anchor["href"])

    # Playwright :has-text fallback — BeautifulSoup'ta manuel
    weiter = soup.select_one('a[href*="gtp"]')
    if weiter and "weiter" in weiter.get_text(strip=True).lower():
        return urljoin(current_url, weiter["href"])

    return None
