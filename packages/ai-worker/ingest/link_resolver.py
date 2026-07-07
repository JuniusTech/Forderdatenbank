"""target:/BMWI/... referanslarını lokal XML dosyalarına çözer."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from ingest.xml_utils import (
    decode_richtext_html,
    extract_classified_links,
    extract_link_list,
    extract_richtext,
    extract_string,
    find_property,
    parse_xml,
)

LABEL_CLASSIFIERS = {
    "Foerderart",
    "Foerderberechtigte",
    "Foerderbereich",
    "Foerdergebiet",
    "Foerdergeber",
    "Unternehmensgroesse",
}


class LinkResolver:
    def __init__(self, export_root: Path):
        self.export_root = export_root.resolve()
        self._roots: dict[str, ET.Element] = {}

    def target_to_path(self, href: str) -> Path:
        rel = href.removeprefix("target:/").lstrip("/")
        if rel.startswith("BMWI/"):
            rel = rel[len("BMWI/") :]
        return self.export_root / f"{rel}.xml"

    def load_root(self, href: str) -> ET.Element | None:
        if href in self._roots:
            return self._roots[href]
        path = self.target_to_path(href)
        if not path.is_file():
            return None
        root = parse_xml(path)
        self._roots[href] = root
        return root

    def slug_from_href(self, href: str) -> str:
        return href.rstrip("/").rsplit("/", 1)[-1]

    def _label_from_bundle(self, slug: str) -> str | None:
        bundle_path = self.export_root / "_config/ResourceBundleEntries/Labels/FDB" / f"{slug}.xml"
        if not bundle_path.is_file():
            return None
        root = parse_xml(bundle_path)
        prop = find_property(root, "gsb:value")
        inner = decode_richtext_html(prop)
        if not inner:
            return None
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(inner, "html.parser")
        for row in soup.select("table tr"):
            cells = [cell.get_text(strip=True) for cell in row.find_all("td")]
            if len(cells) >= 2 and cells[0] not in {"de", "en"}:
                return cells[0]
        return None

    def resolve_label(self, href: str) -> str:
        slug = self.slug_from_href(href)
        label = self._label_from_bundle(slug)
        if label:
            return label
        root = self.load_root(href)
        if root is not None:
            title = extract_richtext(find_property(root, "gsb:title"))
            if title and title != slug:
                return title
        return slug.replace("_", " ")

    def resolve_labels(self, hrefs: list[str]) -> list[str]:
        labels: list[str] = []
        seen: set[str] = set()
        for href in hrefs:
            label = self.resolve_label(href)
            if label not in seen:
                seen.add(label)
                labels.append(label)
        return labels

    def resolve_external_link(self, href: str) -> dict[str, str] | None:
        root = self.load_root(href)
        if root is None:
            return None
        url = extract_string(find_property(root, "gsb:url"))
        if not url:
            return None
        title = extract_richtext(find_property(root, "gsb:title")) or self.slug_from_href(href)
        return {"title": title, "url": url, "target": href}

    def resolve_external_links(self, hrefs: list[str]) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for href in hrefs:
            item = self.resolve_external_link(href)
            if item and item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                links.append(item)
        return links

    def resolve_address(self, href: str) -> dict[str, str] | None:
        root = self.load_root(href)
        if root is None:
            return None
        road = extract_string(find_property(root, "gsb:road"))
        house = extract_string(find_property(root, "gsb:houseId"))
        city = extract_string(find_property(root, "gsb:city"))
        zip_code = extract_string(find_property(root, "gsb:zipCode"))
        street = f"{road} {house}".strip() if road else None
        return {
            "street": street or "",
            "city": city or "",
            "zip_code": zip_code or "",
            "title": extract_richtext(find_property(root, "gsb:title")) or self.slug_from_href(href),
        }

    def resolve_contact(self, href: str) -> dict | None:
        root = self.load_root(href)
        if root is None:
            return None

        contact = {
            "name": extract_richtext(find_property(root, "gsb:title")) or self.slug_from_href(href),
            "email": extract_string(find_property(root, "gsb:email")),
            "phone": extract_string(find_property(root, "gsb:phone")),
            "fax": extract_string(find_property(root, "gsb:fax")),
            "website": None,
            "address": None,
        }

        website_links = extract_link_list(find_property(root, "gsb:website"))
        if website_links:
            external = self.resolve_external_link(website_links[0])
            if external:
                contact["website"] = external["url"]

        address_links = extract_classified_links(find_property(root, "gsb:cl2Addresses")).get("Adresse", [])
        if address_links:
            contact["address"] = self.resolve_address(address_links[0])

        return contact

    def resolve_provider_name(self, href: str) -> str | None:
        root = self.load_root(href)
        if root is None:
            return None
        return extract_richtext(find_property(root, "gsb:title")) or self.slug_from_href(href)
