"""GSG XML yardımcıları — RichText, property okuma, sınıflandırma linkleri."""

from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

XLINK = "{http://www.w3.org/1999/xlink}href"


def parse_xml(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def find_property(root: ET.Element, name: str) -> ET.Element | None:
    for prop in root.findall("property"):
        if prop.get("name") == name:
            return prop
    return None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def decode_richtext_html(prop: ET.Element | None) -> str:
    if prop is None:
        return ""
    text_elem = prop.find("text")
    if text_elem is None or not text_elem.text:
        return ""
    raw = html.unescape(text_elem.text)
    match = re.search(r"<!\[CDATA\[(.*)\]\]>", raw, re.DOTALL)
    return match.group(1) if match else raw


def extract_richtext(prop: ET.Element | None) -> str:
    inner = decode_richtext_html(prop)
    if not inner.strip():
        return ""
    soup = BeautifulSoup(inner, "html.parser")
    return _normalize_text(soup.get_text(separator=" "))


def extract_string(prop: ET.Element | None) -> str | None:
    if prop is None:
        return None
    value_elem = prop.find("value")
    if value_elem is None or value_elem.text is None:
        return None
    return value_elem.text.strip()


def extract_date(prop: ET.Element | None) -> datetime | None:
    raw = extract_string(prop)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _classifier_name(href: str) -> str:
    return href.rstrip("/").rsplit("/", 1)[-1]


def extract_classified_links(prop: ET.Element | None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if prop is None:
        return result

    for link_list in prop.findall(".//classifiedLinkList"):
        classifier_links = link_list.findall("./classifierLinks/link")
        item_links = link_list.findall("./links/link")
        if not classifier_links:
            continue
        classifier_href = classifier_links[0].get(XLINK, "")
        classifier = _classifier_name(classifier_href)
        hrefs = [link.get(XLINK, "") for link in item_links if link.get(XLINK)]
        if hrefs:
            result[classifier] = hrefs
    return result


def extract_link_list(prop: ET.Element | None) -> list[str]:
    if prop is None:
        return []
    return [link.get(XLINK, "") for link in prop.findall(".//links/link") if link.get(XLINK)]


def region_from_program_path(path: Path) -> str:
    parts = path.parts
    try:
        idx = parts.index("Foerderprogramm")
    except ValueError:
        return "unknown"
    if idx + 1 >= len(parts):
        return "unknown"
    region_type = parts[idx + 1]
    if region_type == "Land" and idx + 2 < len(parts):
        return parts[idx + 2]
    return region_type


def build_raw_text(parts: dict[str, str]) -> str:
    blocks = [parts[k] for k in ("summary", "bodyText", "regulatoryFWork", "procDescription", "procMethod") if parts.get(k)]
    return "\n\n".join(blocks)


def compute_program_hash(payload: dict[str, Any]) -> str:
    import hashlib
    import json

    def _default(obj: Any) -> str:
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"JSON serializable değil: {type(obj)!r}")

    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
