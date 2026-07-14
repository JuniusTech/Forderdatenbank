"""PDF → düz metin (Playwright Download / binary response için)."""

from __future__ import annotations

import html as html_module
import logging
import re
from io import BytesIO

logger = logging.getLogger(__name__)


def is_pdf_url(url: str) -> bool:
    path = (url or "").split("?", 1)[0].lower()
    return path.endswith(".pdf")


def extract_pdf_text(data: bytes, *, max_pages: int = 25) -> str:
    """PDF binary → text. pypdf yoksa boş string."""
    if not data or len(data) < 20:
        return ""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("pypdf not installed — cannot extract PDF text")
        return ""
    try:
        reader = PdfReader(BytesIO(data))
        parts: list[str] = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t.strip():
                parts.append(t)
        return "\n".join(parts).strip()
    except Exception as exc:
        logger.warning("PDF extract failed: %s", exc.__class__.__name__)
        return ""


def pdf_bytes_to_html(data: bytes, *, source_url: str = "") -> str:
    """Status-heuristik / AI için HTML sarmalayıcı."""
    text = extract_pdf_text(data)
    if not text:
        return ""
    # Aşırı whitespace sıkıştır
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    escaped = html_module.escape(text[:80_000])
    url_note = html_module.escape(source_url) if source_url else ""
    return (
        f"<html><head><title>PDF {url_note}</title></head>"
        f"<body><pre>{escaped}</pre></body></html>"
    )
