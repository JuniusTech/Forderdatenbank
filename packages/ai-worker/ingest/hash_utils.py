import hashlib
import re

from bs4 import BeautifulSoup

from ingest.selectors import DETAIL_DOC_INFO, DETAIL_TAB1, DETAIL_TAB2, DETAIL_TAB3


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def extract_hash_blocks(html: str) -> tuple[str, str, str, str]:
    soup = BeautifulSoup(html, "html.parser")

    def block_text(selector: str) -> str:
        el = soup.select_one(selector)
        if el is None:
            return ""
        return _normalize_text(el.get_text(separator=" "))

    return (
        block_text(DETAIL_DOC_INFO),
        block_text(DETAIL_TAB1),
        block_text(DETAIL_TAB2),
        block_text(DETAIL_TAB3),
    )


def compute_content_hash(doc_info: str, tab1: str, tab2: str, tab3: str) -> str:
    combined = "\n".join([doc_info, tab1, tab2, tab3])
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def compute_content_hash_from_html(html: str) -> str:
    blocks = extract_hash_blocks(html)
    return compute_content_hash(*blocks)
