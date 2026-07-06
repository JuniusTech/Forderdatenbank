from bs4 import BeautifulSoup

from ingest.url_utils import normalize_detail_url


def get_next_page_url(html: str, site_base: str, current_page: int = 1) -> str | None:
    """Sonraki liste sayfası URL'si — href'ten oku, site köküne göre birleştir."""
    soup = BeautifulSoup(html, "html.parser")

    def resolve(href: str) -> str:
        return normalize_detail_url(href, site_base)

    # 1. "weiter" / "Weiter" linki
    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(strip=True).lower()
        href = anchor["href"]
        if text == "weiter" and "gtp" in href:
            return resolve(href)

    # 2. Sonraki sayfa numarası (2, 3, ...)
    next_num = str(current_page + 1)
    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(strip=True)
        href = anchor["href"]
        if text == next_num and "gtp" in href:
            return resolve(href)

    return None
