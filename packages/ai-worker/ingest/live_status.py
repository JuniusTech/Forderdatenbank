"""Canlı application_url HTML — Katman 3 status zenginleştirme."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
import requests

from ingest.deadline_parser import CLOSED_KEYWORD_RE, GERMAN_MONTHS, scan_program_fields
from ingest.http_client import HttpClient

# IBB / Förderstelle sayfalarında sık görülen kapalı-banner kalıpları
LIVE_CLOSED_PATTERNS = [
    re.compile(r"keine\s+antragstellung\s+möglich", re.I),
    re.compile(r"keine\s+neuen\s+anträge", re.I),
    re.compile(r"seit\s+dem\s+(\d{2})\.(\d{2})\.(\d{4})\s+ist\s+(?:keine\s+antragstellung|eine\s+antragsstellung\s+nicht\s+mehr\s+möglich)", re.I),
    re.compile(r"antragstellung\s+(?:ist\s+)?(?:daher\s+)?(?:derzeit\s+)?nicht\s+(?:mehr\s+)?möglich", re.I),
    re.compile(r"derzeit\s+ist\s+eine\s+antragstellung[^.]{0,40}nicht\s+möglich", re.I),
    re.compile(r"mittel\s+(?:im\s+\w+\s+)?(?:sind|ist)\s+(?:vollständig\s+)?ausgeschöpft", re.I),
    re.compile(r"programm\s+(?:ist\s+)?(?:derzeit\s+)?(?:geschlossen|beendet|ausgelaufen)", re.I),
    re.compile(r"antragsstopp|vorübergehend\s+keine\s+anträge", re.I),
]

# HTTP 200 ama içerik hata sayfası (L-Bank vb.)
ERROR_PAGE_PATTERNS = [
    re.compile(r"\bfehlerseite\b", re.I),
    re.compile(r"seite\s+existiert\s+nicht\s+mehr", re.I),
    re.compile(r"diese\s+seite\s+existiert\s+nicht", re.I),
    re.compile(r"datei\s+oder\s+verzeichnis\s+wurde\s+nicht\s+gefunden", re.I),
]

VALIDITY_UNTIL_RE = re.compile(
    r"(?:richtlinie\s+)?(?:ist\s+)?(?:gültig|gueltig)\s+bis\s+(?:zum\s+)?"
    r"(\d{1,2})\.\s*"
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})",
    re.I,
)

VALID_UNTIL_TRAILING_RE = re.compile(
    r"bis\s+zum\s+(\d{1,2})\.\s*"
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})\s+(?:gültig|gueltig)",
    re.I,
)

BEFRISTET_UNTIL_RE = re.compile(
    r"befristet\s+bis\s+(?:längstens\s+)?(?:zum\s+)?(\d{1,2})\.\s*"
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})",
    re.I,
)

PARTNER_BANK_RE = re.compile(
    r"finanzierungspartner|antrag\s+(?:beim|über)\s+(?:ihren?\s+)?finanzierungspartner",
    re.I,
)

DAUERFOERDERUNG_RE = re.compile(
    r"dauerförderung|laufendes\s+programm|seit\s+\d{4}\s+laufend(?:es)?|kontinuierlich",
    re.I,
)

ONLINE_ANTAG_RE = re.compile(
    r"online-?antrag|foerderverfahren\.[a-z0-9.-]+\.[a-z]{2,}|hier\s+können\s+sie\s+den\s+online-antrag",
    re.I,
)

ANTRAGSFORMULAR_ACTIVE_RE = re.compile(
    r"antragsformular\s+(?:landesmittel|zum\s+download|\(pdf\)|herunterladen)",
    re.I,
)

LAUFENDES_FOERDERPROGRAMM_RE = re.compile(
    r"seit\s+\d+\s+jahren.*förderprogramm|aktion\s+100|laufendes\s+förderprogramm",
    re.I,
)

ANTRAG_BEHOERDE_RE = re.compile(
    r"antrag\s+bei\s+(?:den\s+)?landratsämtern|"
    r"an\s+die\s+regional\s+zuständigen\s+landratsämter|"
    r"landratsämter\.?\s+weitere\s+informationen",
    re.I,
)

FOERDERZUSAGE_RE = re.compile(
    r"förderzusage\s+von\s+(?:fünf|\d+)\s+jahren|langfristige\s+förderzusage",
    re.I,
)

ZUWENDUNG_PROGRAMM_RE = re.compile(
    r"zuwendungen\s+für\s+(?:den\s+)?(?:theoretischen\s+und\s+praktischen|theoretischen|praktischen)\s+unterricht",
    re.I,
)

AUSFALLBUERGSCHAFT_RE = re.compile(
    r"ausfallbürgschaften\s+bis\s+zu\s+\d+\s*%",
    re.I,
)

UEBS_FOERDERUNG_RE = re.compile(
    r"förderung\s+von\s+überbetrieblichen\s+berufsbildungsstätten|\(übs\)",
    re.I,
)

ROLLING_ANTRAGSFRIST_RE = re.compile(
    r"antragsfrist\s+beträgt\s+\d+\s+woche|zwei\s+wochen\s+vor\s+(?:dem\s+)?(?:geplanten\s+)?kursbeginn",
    re.I,
)

FOERDERPORTAL_ANTAG_RE = re.compile(
    r"antragstellung\s+(?:ist\s+)?(?:über\s+)?(?:das\s+)?förderportal|"
    r"online-portal\s+der\s+tab|über\s+das\s+online-portal",
    re.I,
)

ANTRAGSSTICHTAG_RE = re.compile(
    r"(?:nächster\s+)?antragsstichtag\s+ist\s+am\s+(\d{2})\.(\d{2})\.(\d{4})",
    re.I,
)

JEDERZEIT_ANTRAG_RE = re.compile(
    r"antragstellung\s+ist\s+(?:hier\s+)?jederzeit\s+möglich",
    re.I,
)

DIGITALE_ANTRAG_KUERZE_RE = re.compile(
    r"digitale\s+antragstellung\s+ist\s+in\s+kürze\s+möglich",
    re.I,
)

AUFTRAGSGARANTIE_RE = re.compile(r"auftragsgarantien\s+bieten\s+wir", re.I)

FORM_ONLY_RE = re.compile(
    r"ansprechpartner\s+(?:vor\s+ort|liste)|produktauswahl|formular\s+zum\s+ausfüllen|"
    r"nur\s+(?:formulare|vordrucke)|anträge\s+und\s+formulare",
    re.I,
)

_STRIP_TAGS = ("script", "style", "noscript", "nav", "footer", "header")
_STRIP_SELECTORS = (
    "[hidden]",
    "[aria-hidden='true']",
    "[class*='cookie']",
    "[class*='consent']",
    "[id*='cookie']",
    "[id*='consent']",
)


@dataclass
class LiveStatusResult:
    url: str
    http_status: int
    final_url: str
    status: str
    reason: str
    closure_date: date | None = None
    snippet: str | None = None
    method: str = "regex"
    funding_period: str | None = None
    confidence: str | None = None
    evidence_quote: str | None = None
    canonical_url: str | None = None
    redirect_type: str | None = None


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    for sel in _STRIP_SELECTORS:
        for el in soup.select(sel):
            el.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def html_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title:
        return soup.title.get_text(strip=True)
    return ""


def _parse_german_date(day: str, month: str, year: str) -> date:
    month_num = GERMAN_MONTHS[month.lower().replace("ä", "ä")]
    return date(int(year), month_num, int(day))


def _snippet(text: str, start: int, end: int, *, limit: int = 220) -> str:
    return text[max(0, start) : end + 80][:limit]


def detect_error_page(*, html: str, text: str) -> tuple[str, str] | None:
    title = html_title(html)
    haystack = f"{title} {text[:2500]}"
    for pat in ERROR_PAGE_PATTERNS:
        m = pat.search(haystack)
        if m:
            return "closed", f"Fehlerseite: {m.group(0)[:80]}"
    return None


def apply_live_heuristics(
    text: str,
    *,
    reference: date | None = None,
) -> tuple[str, str, date | None, str | None] | None:
    """Regex/AI öncesi — ground-truth'tan çıkarılan ek kurallar."""
    ref = reference or date.today()

    m = ANTRAGSSTICHTAG_RE.search(text)
    if m:
        stichtag = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        snippet = _snippet(text, m.start(), m.end())
        if stichtag >= ref:
            return (
                "laufend",
                f"Antragsstichtag {stichtag.isoformat()}",
                stichtag,
                snippet,
            )
        return (
            "closed",
            f"Antragsstichtag verstrichen ({stichtag.isoformat()})",
            stichtag,
            snippet,
        )

    for pat in (VALIDITY_UNTIL_RE, VALID_UNTIL_TRAILING_RE, BEFRISTET_UNTIL_RE):
        m = pat.search(text)
        if m:
            valid_until = _parse_german_date(m.group(1), m.group(2), m.group(3))
            snippet = _snippet(text, m.start(), m.end())
            if valid_until >= ref:
                return (
                    "laufend",
                    f"Gültigkeit bis {valid_until.isoformat()}",
                    valid_until,
                    snippet,
                )
            return (
                "closed",
                f"Gültigkeit endete am {valid_until.isoformat()}",
                valid_until,
                snippet,
            )

    if PARTNER_BANK_RE.search(text) and len(text) > 150:
        m = PARTNER_BANK_RE.search(text)
        snippet = _snippet(text, m.start(), m.end())
        return (
            "active",
            "Antrag über Finanzierungspartner — Programmseite aktiv",
            None,
            snippet,
        )

    if DAUERFOERDERUNG_RE.search(text) and len(text) > 80:
        m = DAUERFOERDERUNG_RE.search(text)
        snippet = _snippet(text, m.start(), m.end())
        return (
            "active",
            "Dauerförderung / laufendes Programm ohne festes Enddatum",
            None,
            snippet,
        )

    for pat, reason in (
        (ROLLING_ANTRAGSFRIST_RE, "Rollierende Antragsfrist — Dauerprogramm"),
        (FOERDERPORTAL_ANTAG_RE, "Antrag über Förderportal"),
        (JEDERZEIT_ANTRAG_RE, "Antragstellung jederzeit möglich"),
        (DIGITALE_ANTRAG_KUERZE_RE, "Digitale Antragstellung demnächst — Programm aktiv"),
        (AUFTRAGSGARANTIE_RE, "LfA Auftragsgarantien — aktives Produkt"),
        (ONLINE_ANTAG_RE, "Online-Antragsverfahren aktiv"),
        (ANTRAGSFORMULAR_ACTIVE_RE, "Antragsformular verfügbar — Programm aktiv"),
        (LAUFENDES_FOERDERPROGRAMM_RE, "Laufendes Förderprogramm ohne Enddatum"),
        (ANTRAG_BEHOERDE_RE, "Antrag bei Behörde — laufendes Förderinstrument"),
        (FOERDERZUSAGE_RE, "Langfristige Förderzusage — Programm aktiv"),
        (ZUWENDUNG_PROGRAMM_RE, "Zuwendungsprogramm mit laufender Antragstellung"),
        (AUSFALLBUERGSCHAFT_RE, "Aktives Bürgschaftsprodukt"),
        (UEBS_FOERDERUNG_RE, "ÜBS-Förderprogramm aktiv"),
    ):
        m = pat.search(text)
        if m and len(text) > 50:
            snippet = _snippet(text, m.start(), m.end())
            return ("active", reason, None, snippet)

    return None


def _redirect_metadata(url: str, final_url: str, status: str) -> tuple[str | None, str | None]:
    if url.rstrip("/") == final_url.rstrip("/"):
        return None, None
    if status == "unknown":
        return None, None
    return final_url, "consolidated"


def _parent_url(url: str) -> str | None:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path or path.count("/") < 1:
        return None
    parent_path = path.rsplit("/", 1)[0]
    if not parent_path:
        return None
    return urlunparse((parsed.scheme, parsed.netloc, parent_path + "/", "", "", ""))


def _title_relevant(text: str, title: str) -> bool:
    if not title:
        return True
    words = [w.lower() for w in re.findall(r"\w{4,}", title)[:4]]
    if not words:
        return True
    hay = text.lower()
    return any(w in hay for w in words)


def _should_try_parent(*, text: str, status: str, program_title: str, url: str) -> bool:
    if status != "unknown" or not _parent_url(url):
        return False
    if FORM_ONLY_RE.search(text):
        return True
    if program_title and not _title_relevant(text, program_title):
        return True
    return False


def _evaluate_fetched_page(
    *,
    html: str,
    reference: date | None,
    use_ai_fallback: bool,
    program_title: str,
    page_url: str,
) -> tuple[str, str, date | None, str | None, str, str | None, str | None]:
    text = html_to_text(html)
    funding_period: str | None = None
    confidence: str | None = None
    error_hit = detect_error_page(html=html, text=text)
    if error_hit:
        return (*error_hit, None, text[:220], "regex", funding_period, confidence)

    prog_status, reason, closure, snippet = scan_live_text(text, reference=reference)
    method = "regex"
    if prog_status == "unknown":
        heuristic = apply_live_heuristics(text, reference=reference)
        if heuristic:
            prog_status, reason, closure, snippet = heuristic
            method = "heuristic"

    if prog_status == "unknown" and use_ai_fallback:
        from ai.page_extractor import ai_fallback_available, extract_page_with_ai

        ai = extract_page_with_ai(
            page_text=text,
            program_title=program_title or page_url,
            page_url=page_url,
            reference=reference,
        )
        if ai:
            prog_status = ai.status
            reason = f"{ai.method} ({ai.confidence}): {ai.reason}"
            closure = ai.application_deadline
            snippet = ai.evidence_quote
            method = ai.method
            funding_period = ai.funding_period
            confidence = ai.confidence
            if prog_status == "unknown" and ai.confidence == "low":
                heuristic = apply_live_heuristics(text, reference=reference)
                if heuristic:
                    prog_status, reason, closure, snippet = heuristic
                    method = "heuristic"
            if prog_status == "unknown" and detect_error_page(html=html, text=text):
                prog_status, reason = detect_error_page(html=html, text=text)
                method = "regex"
        elif use_ai_fallback and not ai_fallback_available():
            reason = f"{reason} (AI: weder Ollama noch ANTHROPIC_API_KEY)"

    return prog_status, reason, closure, snippet, method, funding_period, confidence


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
    client=None,
    reference: date | None = None,
    timeout: float = 12.0,
    program_title: str = "",
    use_ai_fallback: bool = False,
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

    if status_code in {404, 410}:
        return LiveStatusResult(
            url=url,
            http_status=status_code,
            final_url=final_url,
            status="closed",
            reason=f"HTTP {status_code}: Seite nicht gefunden",
            method="regex",
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
    prog_status, reason, closure, snippet, method, funding_period, confidence = _evaluate_fetched_page(
        html=html,
        reference=reference,
        use_ai_fallback=use_ai_fallback,
        program_title=program_title,
        page_url=final_url,
    )
    resolved_url = final_url
    resolved_canonical: str | None = None

    if _should_try_parent(text=text, status=prog_status, program_title=program_title, url=final_url):
        parent = _parent_url(final_url)
        if parent and parent.rstrip("/") != final_url.rstrip("/"):
            try:
                p_code, p_final, p_html = http.get(parent, timeout=timeout)
            except requests.RequestException:
                p_code, p_final, p_html = 0, parent, ""
            if p_code == 200 and p_html.strip():
                p_status, p_reason, p_closure, p_snippet, p_method, _, _ = _evaluate_fetched_page(
                    html=p_html,
                    reference=reference,
                    use_ai_fallback=use_ai_fallback,
                    program_title=program_title,
                    page_url=p_final,
                )
                if p_status != "unknown":
                    prog_status, reason, closure, snippet, method = (
                        p_status,
                        f"{p_reason} (übergeordnete Seite)",
                        p_closure,
                        p_snippet,
                        p_method,
                    )
                    resolved_url = p_final
                    resolved_canonical = p_final

    canonical_url, redirect_type = _redirect_metadata(url, resolved_url, prog_status)
    if resolved_canonical and prog_status != "unknown":
        canonical_url = resolved_canonical
        redirect_type = "parent_page"
    return LiveStatusResult(
        url=url,
        http_status=status_code,
        final_url=resolved_url,
        status=prog_status,
        reason=reason,
        closure_date=closure,
        snippet=snippet,
        method=method,
        funding_period=funding_period,
        confidence=confidence,
        evidence_quote=snippet,
        canonical_url=canonical_url,
        redirect_type=redirect_type,
    )
