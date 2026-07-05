from urllib.parse import urljoin


def normalize_detail_url(href: str, site_base: str) -> str:
    """Detay linkini mutlak URL'e çevir.

    Site href'leri üç formda gelebilir:
    - /FDB/Content/...          → site köküne göre
    - FDB/Content/...           → site köküne göre (başında / yok — canlı sitede bu)
    - https://...               → olduğu gibi
    """
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    base = site_base.rstrip("/")
    if href.startswith("/"):
        return f"{base}{href}"
    return f"{base}/{href}"
