"""Program başvuru durumu — çoklu alan deadline parse + status çözümleme."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

GERMAN_MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

CLOSED_KEYWORD_RE = re.compile(
    r"keine\s+antragstellung|antragstellung\s+(?:ist\s+)?nicht\s+(?:mehr\s+)?möglich|"
    r"nicht\s+mehr\s+möglich|programm\s+(?:ist\s+)?beendet|antragsfrist\s+.*abgelaufen|"
    r"förderung\s+.*ausgelaufen|ausgeschrieben\s+.*beendet",
    re.IGNORECASE,
)

# Program sonu değil — atla
SKIP_CONTEXT_RE = re.compile(
    r"bis\s+zum\s+(?:ende\s+der\s+)?(?:zweckbindungs|bewilligungs)frist|"
    r"bis\s+zum\s+\d{1,2}\.\s+\w+\s+\d{4}\s+nur\s+für|"
    r"spätestens\s+\d+\s+monate\s+nach",
    re.IGNORECASE,
)

STRONG_END_RE = re.compile(
    r"(?:gilt\s+für\s+alle\s+anträge|geltungsdauer|antragsfrist|laufzeit\s+dieser\s+förderrichtlinie)"
    r"[^.]{0,120}?bis\s+zum\s+(\d{1,2})\.\s*"
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)

WINDOW_RE = re.compile(
    r"(?:zeitraum|frist|periode)?\s*vom\s+(\d{1,2})\.(\d{1,2})\.(\d{4})\s+bis\s+zum\s+"
    r"(\d{1,2})\.(\d{1,2})\.(\d{4})",
    re.IGNORECASE,
)

WINDOW_DE_RE = re.compile(
    r"vom\s+(\d{1,2})\.\s*"
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})\s+bis\s+zum\s+(\d{1,2})\.\s*"
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)

GENERIC_END_RE = re.compile(
    r"bis\s+zum\s+(\d{1,2})\.\s*"
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)

SUBMIT_END_RE = re.compile(
    r"bis\s+zum\s+(\d{1,2})\.\s*"
    r"(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r"\s+(\d{4})[^.]{0,40}(?:eingehen|einreichen|gestellt)",
    re.IGNORECASE,
)

ISO_DATE_PROP_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


@dataclass
class DeadlineSignal:
    kind: str  # closed_keyword | application_end | application_window
    source: str
    end: date | None = None
    start: date | None = None
    detail: str = ""
    weight: int = 1


@dataclass
class StatusResult:
    status: str  # active | closed | laufend | unknown
    reason: str
    signals: list[DeadlineSignal] = field(default_factory=list)
    application_end: date | None = None
    application_start: date | None = None


def _parse_german_date(day: str, month: str, year: str) -> date:
    month_num = GERMAN_MONTHS[month.lower().replace("ä", "ä")]
    return date(int(year), month_num, int(day))


def _parse_dmy(day: str, month: str, year: str) -> date:
    return date(int(year), int(month), int(day))


def scan_text_field(text: str, source: str) -> list[DeadlineSignal]:
    if not text or not text.strip():
        return []

    signals: list[DeadlineSignal] = []
    normalized = re.sub(r"\s+", " ", text)

    if CLOSED_KEYWORD_RE.search(normalized):
        signals.append(
            DeadlineSignal(
                kind="closed_keyword",
                source=source,
                detail=CLOSED_KEYWORD_RE.search(normalized).group(0)[:80],
                weight=100,
            )
        )

    for match in STRONG_END_RE.finditer(normalized):
        snippet = match.group(0)
        if SKIP_CONTEXT_RE.search(snippet):
            continue
        end = _parse_german_date(match.group(1), match.group(2), match.group(3))
        signals.append(
            DeadlineSignal(
                kind="application_end",
                source=source,
                end=end,
                detail=snippet[:100],
                weight=90,
            )
        )

    for match in SUBMIT_END_RE.finditer(normalized):
        snippet = match.group(0)
        if SKIP_CONTEXT_RE.search(snippet):
            continue
        end = _parse_german_date(match.group(1), match.group(2), match.group(3))
        signals.append(
            DeadlineSignal(
                kind="application_end",
                source=source,
                end=end,
                detail=snippet[:100],
                weight=85,
            )
        )

    for match in WINDOW_DE_RE.finditer(normalized):
        snippet = match.group(0)
        start = _parse_german_date(match.group(1), match.group(2), match.group(3))
        end = _parse_german_date(match.group(4), match.group(5), match.group(6))
        weight = 95 if source in {"procInfluence", "procDescription", "procMethod"} else 70
        signals.append(
            DeadlineSignal(
                kind="application_window",
                source=source,
                start=start,
                end=end,
                detail=snippet[:100],
                weight=weight,
            )
        )

    for match in WINDOW_RE.finditer(normalized):
        snippet = match.group(0)
        start = _parse_dmy(match.group(1), match.group(2), match.group(3))
        end = _parse_dmy(match.group(4), match.group(5), match.group(6))
        weight = 95 if source in {"procInfluence", "procDescription", "procMethod"} else 70
        signals.append(
            DeadlineSignal(
                kind="application_window",
                source=source,
                start=start,
                end=end,
                detail=snippet[:100],
                weight=weight,
            )
        )

    # summary/bodyText: yalnızca güçlü bağlam veya yüksek öncelikli alanlarda generic "bis zum"
    allow_generic = source in {"procInfluence", "procDescription", "procMethod", "frist"}
    if allow_generic or source in {"bodyText", "regulatoryFWork"}:
        generic_weight = 80 if source == "bodyText" else 60 if source == "regulatoryFWork" else 75
        for match in GENERIC_END_RE.finditer(normalized):
            snippet = _context(normalized, match.start(), 80)
            if SKIP_CONTEXT_RE.search(snippet):
                continue
            # bodyText'te zayıf generic — yalnızca Antrag/Geltungsdauer yakınında
            if source == "bodyText" and not re.search(
                r"geltungsdauer|anträge|antragstellung|förderrichtlinie|laufzeit", snippet, re.I
            ):
                continue
            end = _parse_german_date(match.group(1), match.group(2), match.group(3))
            signals.append(
                DeadlineSignal(
                    kind="application_end",
                    source=source,
                    end=end,
                    detail=snippet[:100],
                    weight=generic_weight,
                )
            )

    return signals


def _context(text: str, pos: int, size: int) -> str:
    start = max(0, pos - size // 2)
    end = min(len(text), pos + size // 2)
    return text[start:end]


def scan_program_fields(
    fields: dict[str, str],
    *,
    reference: date | None = None,
) -> StatusResult:
    """Tüm metin alanlarını tara; çelişkide en kısıtlayıcı (en erken bitiş / kapalı) kazanır."""
    ref = reference or date.today()
    all_signals: list[DeadlineSignal] = []

    # Öncelik sırası — summary tek başına açık sayılmaz, bodyText/procInfluence baskın
    field_order = [
        "frist",
        "procInfluence",
        "procDescription",
        "procMethod",
        "bodyText",
        "regulatoryFWork",
        "summary",
    ]
    for name in field_order:
        text = fields.get(name) or ""
        all_signals.extend(scan_text_field(text, name))

    if any(s.kind == "closed_keyword" for s in all_signals):
        return StatusResult(
            status="closed",
            reason="Explizite Schließung im Programmtext",
            signals=all_signals,
        )

    end_dates: list[tuple[date, DeadlineSignal]] = []
    windows: list[DeadlineSignal] = []

    for sig in all_signals:
        if sig.kind == "application_end" and sig.end:
            end_dates.append((sig.end, sig))
        elif sig.kind == "application_window" and sig.end:
            windows.append(sig)
            end_dates.append((sig.end, sig))

    if not end_dates and not windows:
        return StatusResult(
            status="unknown",
            reason="Kein belastbarer Antragsfrist-Hinweis",
            signals=all_signals,
        )

    # En kısıtlayıcı: en erken bitiş tarihi (çelişkide erken tarih kazanır → kapalı)
    end_dates.sort(key=lambda x: x[0])
    earliest_end, earliest_sig = end_dates[0]

    best_window: DeadlineSignal | None = None
    if windows:
        windows.sort(key=lambda w: (w.start or date.min, w.weight), reverse=True)
        best_window = max(windows, key=lambda w: w.weight)

    application_start = best_window.start if best_window else None
    application_end = earliest_end

    if earliest_end < ref:
        return StatusResult(
            status="closed",
            reason=f"Antragsfrist abgelaufen ({earliest_end.isoformat()}, Quelle: {earliest_sig.source})",
            signals=all_signals,
            application_end=application_end,
            application_start=application_start,
        )

    if best_window and best_window.start and best_window.end:
        if best_window.start <= ref <= best_window.end:
            return StatusResult(
                status="laufend",
                reason=f"Antragszeitraum offen ({best_window.start} – {best_window.end})",
                signals=all_signals,
                application_end=application_end,
                application_start=application_start,
            )

    return StatusResult(
        status="active",
        reason=f"Antragsfrist in der Zukunft oder offen (bis {application_end})",
        signals=all_signals,
        application_end=application_end,
        application_start=application_start,
    )


def parse_frist_property(raw: str | None) -> str:
    """gsb:frist veya Foerdertermin çözümlemesi için ham metin."""
    if not raw:
        return ""
    iso = ISO_DATE_PROP_RE.match(raw.strip())
    if iso:
        return raw
    return raw
