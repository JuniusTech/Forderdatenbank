"""Canlı application_url HTML — Katman 3 status zenginleştirme."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup
import requests

from ingest.deadline_parser import CLOSED_KEYWORD_RE, scan_program_fields
from ingest.http_client import HttpClient

# IBB / Förderstelle sayfalarında sık görülen kapalı-banner kalıpları
LIVE_CLOSED_PATTERNS = [
  re.compile(r"keine\s+antragstellung\s+möglich", re.I),
  re.compile(r"seit\s+dem\s+(\d{2})\.(\d{2})\.(\d{4})\s+ist\s+keine\s+antragstellung", re.I),
  re.compile(r"antragstellung\s+(?:ist\s+)?(?:derzeit\s+)?nicht\s+möglich", re.I),
  re.compile(r"programm\s+(?:ist\s+)?(?:derzeit\s+)?(?:geschlossen|beendet|ausgelaufen)", re.I),
]


@dataclass
class LiveStatusResult:
    url: str
    http_status: int
    final_url: str
    status: str
    reason: str
    closure_date: date | None = None
    snippet: str | None = None


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def scan_live_text(text: str, *, reference: date | None = None) -> tuple[str, str, date | None, str | None]:
    """HTML düz metninden status çıkar — XML parser ile aynı kurallar + canlı banner."""
    ref = reference or date.today()

    for pat in LIVE_CLOSED_PATTERNS:
        m = pat.search(text)
        if m:
            closure: date | None = None
            if m.lastindex and m.lastindex >= 3:
                closure = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            snippet = text[max(0, m.start() - 40) : m.end() + 120][:220]
            if closure is None:
                since = re.search(
                    r"seit\s+dem\s+(\d{2})\.(\d{2})\.(\d{4})\s+ist\s+keine\s+antragstellung",
                    snippet,
                    re.I,
                )
                if since:
                    closure = date(int(since.group(3)), int(since.group(2)), int(since.group(1)))
            return "closed", f"Live-Seite: {m.group(0)[:80]}", closure, snippet

    if CLOSED_KEYWORD_RE.search(text):
        m = CLOSED_KEYWORD_RE.search(text)
        snippet = text[max(0, m.start() - 40) : m.end() + 80][:200]
        return "closed", "Live-Seite: Schließungshinweis", None, snippet

    xml_style = scan_program_fields(
        {
            "summary": text[:4000],
            "bodyText": text,
            "procInfluence": "",
            "procDescription": "",
            "procMethod": "",
            "regulatoryFWork": "",
            "frist": "",
        },
        reference=ref,
    )
    return xml_style.status, f"Live-Seite: {xml_style.reason}", xml_style.application_end, None


def check_live_url(
    url: str,
    *,
    client: HttpClient | None = None,
    reference: date | None = None,
    timeout: float = 12.0,
) -> LiveStatusResult:
    http = client or HttpClient()
    try:
        status_code, final_url, html = http.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return LiveStatusResult(
            url=url,
            http_status=0,
            final_url=url,
            status="unknown",
            reason=f"Seite nicht erreichbar: {exc.__class__.__name__}",
        )

    if status_code >= 400 or not html.strip():
        return LiveStatusResult(
            url=url,
            http_status=status_code,
            final_url=final_url,
            status="unknown",
            reason=f"HTTP {status_code}",
        )

    text = html_to_text(html)
    prog_status, reason, closure, snippet = scan_live_text(text, reference=reference)

    return LiveStatusResult(
        url=url,
        http_status=status_code,
        final_url=final_url,
        status=prog_status,
        reason=reason,
        closure_date=closure,
        snippet=snippet,
    )
