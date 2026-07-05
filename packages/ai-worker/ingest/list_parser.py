import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ingest.selectors import CARD, CARD_TITLE_LINK


@dataclass
class ListEntry:
    detail_path: str
    detail_url: str
    title: str
    target_group: str
    funded_area: str


def parse_total_hits(html: str) -> int | None:
    soup = BeautifulSoup(html, "html.parser")
    hits_el = soup.select_one("div.search--hits")
    if hits_el is None:
        return None
    match = re.search(r"([\d.]+)\s+Beitr", hits_el.get_text())
    if not match:
        return None
    return int(match.group(1).replace(".", ""))


def parse_list_page(html: str, base_url: str, current_url: str) -> list[ListEntry]:
    soup = BeautifulSoup(html, "html.parser")
    entries: list[ListEntry] = []

    for card in soup.select(CARD):
        link = card.select_one(CARD_TITLE_LINK)
        if link is None or not link.get("href"):
            continue

        detail_path = link["href"]
        detail_url = urljoin(current_url, detail_path)
        title = link.get_text(strip=True)

        dl = card.select_one("dl.document-info-fundingprogram")
        dds = dl.select("dd") if dl else []
        target_group = dds[0].get_text(strip=True) if len(dds) > 0 else ""
        funded_area = dds[1].get_text(strip=True) if len(dds) > 1 else ""

        entries.append(
            ListEntry(
                detail_path=detail_path,
                detail_url=detail_url,
                title=title,
                target_group=target_group,
                funded_area=funded_area,
            )
        )

    return entries
