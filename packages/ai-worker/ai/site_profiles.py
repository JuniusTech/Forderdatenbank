"""Domain/site karakteristikleri — Playwright + Ollama ipuçları.

Bir kez tanımlanır; her live-check'te URL host'una göre otomatik uygulanır.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SiteProfile:
    """Bir domain ailesinin sayfa davranışı + AI karar ipuçları."""

    domain: str
    # Playwright
    wait_until: str = "domcontentloaded"
    use_inner_text_fallback: bool = False
    try_lowercase_on_404: bool = False
    known_working_subpaths: tuple[str, ...] = ()
    # AI
    page_kind: str = "program"  # program | portal_root | spa | ministry_overview | bank_product
    ai_hints_de: tuple[str, ...] = ()
    # Kök URL (path kısa) program sayfası sayılmaz → unknown bırak / alt sayfa ara
    root_insufficient: bool = False
    # Path fragment'ları → overview/yanlış URL (vi_node, #/public/home, …)
    insufficient_path_markers: tuple[str, ...] = ()
    # Program açıklaması varsa ve kapanış yoksa active tercih et
    prefer_active_if_described: bool = False
    notes: str = ""


# Top unknown domain'lerden + bilinen zor siteler
SITE_PROFILES: dict[str, SiteProfile] = {
    "nbank.de": SiteProfile(
        domain="nbank.de",
        wait_until="networkidle",
        use_inner_text_fallback=True,
        page_kind="spa",
        prefer_active_if_described=True,
        ai_hints_de=(
            "NBank SPA: Inhalt oft erst nach JS sichtbar — Text kann Antragsstichtag, "
            "'Aktuelle Förderprogramme', 'Antragstellung' enthalten.",
            "Fehlende feste Jahresfrist ≠ unknown. Stichtag in der Zukunft → laufend.",
            "'Eine Antragsstellung ist seit dem DATUM nicht mehr möglich' → closed.",
        ),
        notes="React SPA",
    ),
    "aufbaubank.de": SiteProfile(
        domain="aufbaubank.de",
        try_lowercase_on_404=True,
        use_inner_text_fallback=True,
        page_kind="program",
        prefer_active_if_described=True,
        ai_hints_de=(
            "TAB/Aufbaubank: 'Online-Portal der TAB', 'Förderportal', 'Antragstellung möglich' → active.",
            "'Mittel ausgeschöpft' / 'Derzeit ist eine Antragstellung nicht möglich' → closed.",
            "Aktualisierungsdatum allein ≠ closed. Produktbeschreibung ohne Schließung → active.",
        ),
        notes="TAB",
    ),
    "lfa.de": SiteProfile(
        domain="lfa.de",
        known_working_subpaths=(
            "/website/de/foerderangebote/transformation/energie/index.php",
            "/website/de/foerderangebote/finanzierung/risikoentlastungen/index.php",
            "/website/de/foerderangebote/beteiligung/index.php",
        ),
        root_insufficient=True,
        insufficient_path_markers=("/website/de",),
        page_kind="portal_root",
        ai_hints_de=(
            "WICHTIG: lfa.de Root und /website/de/ zeigen nur Video-Teaser — NIE als Programmnachweis.",
            "Echte Inhalte unter /website/de/foerderangebote/... ; PDF-Merkblätter/Rundschreiben OK (pdf_only).",
            "Produktname fehlt in aktueller Kategorie-Liste → eher closed/low als unknown (Umbenennung).",
            "Antrag über Hausbank/Finanzierungspartner → active.",
        ),
        notes="Root/Teaser yetersiz — Claude site-structure 2026-07",
    ),
    "schleswig-holstein.de": SiteProfile(
        domain="schleswig-holstein.de",
        use_inner_text_fallback=True,
        page_kind="ministry_overview",
        prefer_active_if_described=True,
        insufficient_path_markers=("vi_node", "viii_node", "/vi_node", "/viii_node"),
        ai_hints_de=(
            "vi_node/viii_node = Ministeriums-Startseite (News) — NIE canonical, status eher unknown.",
            "fachinhalte/... URLs können echte Programmseiten sein — Titel-Content-Match prüfen.",
            "Richtlinie mit Jahresangabe z.B. (2024-2028) → laufend.",
            "Fehlende Antragsfrist bei Landesprogrammen ist normal → eher active als unknown.",
        ),
        notes="Claude site-structure: vi_node/viii_node wrong_url",
    ),
    "hamburg.de": SiteProfile(
        domain="hamburg.de",
        page_kind="program_detail",
        prefer_active_if_described=True,
        ai_hints_de=(
            "hamburg.de Fachseiten (bsfb etc.): alte URLs redirecten oft korrekt — Inhalt nutzen.",
            "Antragsverfahren + Formulare + Richtlinie ohne Schließung → active.",
            "Fehlende Frist ≠ unknown.",
        ),
    ),
    "metropolregion.hamburg.de": SiteProfile(
        domain="metropolregion.hamburg.de",
        known_working_subpaths=(
            "/ueber-uns/foerderfonds/projektantraege-und-richtlinien-8498",
        ),
        insufficient_path_markers=("/foerderfonds",),
        page_kind="ministry_overview",
        prefer_active_if_described=True,
        ai_hints_de=(
            "/foerderfonds/ Basis = nur Teaser. Echte Anträge unter "
            ".../projektantraege-und-richtlinien-8498.",
            "Antragsformular/Richtlinie Download sichtbar → active (Dauerfonds).",
        ),
        notes="Mehr-Link Anträge und Richtlinien",
    ),
    "foerderportal.wibank.de": SiteProfile(
        domain="foerderportal.wibank.de",
        use_inner_text_fallback=True,
        root_insufficient=True,
        insufficient_path_markers=("#/public/home", "/site/"),
        page_kind="spa_shell",
        prefer_active_if_described=False,
        ai_hints_de=(
            "foerderportal.wibank.de #/public/home = IMMER nur Login/Kundenportal — unknown.",
            "Programminhalt liegt auf wibank.de (/resource/blob/...) oder esf-hessen.de — nicht hier.",
            "Nur Portal-UI ohne Richtlinie → unknown, nicht active raten.",
        ),
        notes="SPA shell — Claude site-structure",
    ),
    "wibank.de": SiteProfile(
        domain="wibank.de",
        page_kind="bank_product",
        prefer_active_if_described=True,
        ai_hints_de=(
            "wibank.de: öffentliche Richtlinien oft als PDF unter /resource/blob/...",
            "Richtlinientext ohne Schließung → active. ESF zusätzlich esf-hessen.de prüfen.",
        ),
    ),
    "lvwa.sachsen-anhalt.de": SiteProfile(
        domain="lvwa.sachsen-anhalt.de",
        page_kind="program_detail",
        prefer_active_if_described=True,
        ai_hints_de=(
            "LVWA Maßnahmenseiten: Gegenstand/Antragsberechtigte/Förderhöhe/Unterlagen — gut strukturiert.",
            "Maßnahmentext + Antragsformular ohne Schließung → active.",
            "Nur Qualitätskriterien-PDF ohne Förderhöhe/Antrag → unknown.",
            "Fehlende Frist ≠ unknown.",
        ),
        notes="Wait 1-2s nach Navigation (stale text)",
    ),
    "umwelt.nrw.de": SiteProfile(
        domain="umwelt.nrw.de",
        root_insufficient=True,
        page_kind="ministry_overview",
        prefer_active_if_described=True,
        ai_hints_de=(
            "umwelt.nrw.de Root = nur Teaser — NIE als Programmnachweis.",
            "Fachpfade (FöNa, Biologische Stationen) können Programminhalt haben.",
            "Manche Programme nur über Pressemitteilungen nachweisbar — dann medium/active vorsichtig.",
            "Explizite 'keine Antragstellung' → closed.",
        ),
    ),
    "mags.nrw": SiteProfile(
        domain="mags.nrw",
        page_kind="ministry_overview",
        prefer_active_if_described=True,
        ai_hints_de=(
            "MAGS NRW: 'Aktion 100', laufende Landesprogramme oft ohne Enddatum → active.",
            "Kurzer Teaser ohne Programmdetails → unknown nur wenn wirklich kein Inhalt.",
        ),
    ),
    "soziales.niedersachsen.de": SiteProfile(
        domain="soziales.niedersachsen.de",
        page_kind="ministry_overview",
        prefer_active_if_described=True,
        ai_hints_de=(
            "Nds. Soziales: Themeneseiten nennen oft Landesprogramme namentlich → active wenn genannt.",
            "Nur allgemeine Jugendhilfe-Übersicht ohne Programmbezug → unknown.",
        ),
    ),
    "bb-h.de": SiteProfile(
        domain="bb-h.de",
        page_kind="bank_product",
        prefer_active_if_described=True,
        ai_hints_de=(
            "Bürgschaftsbank Hessen: Produktseiten für Garantien/Bürgschaften.",
            "Leere Seite oder nur Menü → unknown. Produktkonditionen → active.",
        ),
    ),
    "kfw.de": SiteProfile(
        domain="kfw.de",
        page_kind="bank_product",
        prefer_active_if_described=True,
        ai_hints_de=(
            "KfW: 'Antrag beim Finanzierungspartner' = active (Dauerprodukt).",
            "Keine Antragsfrist auf Produktseite ist normal → nicht unknown.",
        ),
    ),
    "kfw-capital.de": SiteProfile(
        domain="kfw-capital.de",
        known_working_subpaths=("/",),
        page_kind="bank_product",
        prefer_active_if_described=True,
        ai_hints_de=(
            "KfW Capital: Fonds-/Investmentbeschreibung ohne Frist → active.",
            "Fehlerseite auf Unterpfad → unknown (Root ggf. separat).",
        ),
    ),
    "brandenburg-go.de": SiteProfile(
        domain="brandenburg-go.de",
        page_kind="portal_root",
        ai_hints_de=(
            "SICHERHEIT: Domain kann hijacked sein. Fremde Werbe-/Tracking-Seite → unknown, "
            "NIEMALS closed oder active.",
        ),
        notes="Hijack riski",
    ),
    "nasa.de": SiteProfile(
        domain="nasa.de",
        page_kind="portal_root",
        ai_hints_de=("Domain oft unreachable — ohne Text → unknown.",),
        notes="Timeout sık",
    ),
    "ibb.de": SiteProfile(
        domain="ibb.de",
        use_inner_text_fallback=True,
        page_kind="program",
        prefer_active_if_described=True,
        ai_hints_de=(
            "IBB: Infobox 'Keine Antragstellung möglich' → closed.",
            "Produktseite mit Konditionen ohne Schließung → active.",
        ),
    ),
    "aufstiegs-bafoeg.de": SiteProfile(
        domain="aufstiegs-bafoeg.de",
        wait_until="networkidle",
        use_inner_text_fallback=True,
        page_kind="spa",
        prefer_active_if_described=True,
        ai_hints_de=(
            "Aufstiegs-BAföG: SPA — 'Loading...' allein → unknown (Inhalt fehlt).",
            "Wenn Förderbedingungen sichtbar und laufend → active.",
        ),
    ),
    "berlin.de": SiteProfile(
        domain="berlin.de",
        page_kind="ministry_overview",
        prefer_active_if_described=True,
        ai_hints_de=(
            "berlin.de: ESF-Übersichtsseiten ohne Stipendien-Detail → unknown für spezifisches Programm.",
            "Explizite Programmseite mit Antrag → active; 'keine neuen Anträge' → closed.",
        ),
    ),
    "bmwk.de": SiteProfile(
        domain="bmwk.de",
        page_kind="ministry_overview",
        ai_hints_de=(
            "BMWK: CAPTCHA möglich. Pressemitteilung kann Programmstatus enthalten.",
            "Nur Captcha-Text → unknown.",
        ),
    ),
    "bundeswirtschaftsministerium.de": SiteProfile(
        domain="bundeswirtschaftsministerium.de",
        page_kind="ministry_overview",
        ai_hints_de=(
            "CAPTCHA häufig. Bei sichtbarer Förderrichtlinie 2027-2029 → laufend.",
            "Nur Captcha → unknown.",
        ),
    ),
}


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def get_site_profile(url: str) -> SiteProfile | None:
    """En spesifik (en uzun) domain eşleşmesini döndür."""
    host = host_of(url)
    best: SiteProfile | None = None
    best_len = -1
    for domain, profile in SITE_PROFILES.items():
        if host == domain or host.endswith("." + domain):
            if len(domain) > best_len:
                best = profile
                best_len = len(domain)
    return best


def url_is_insufficient(url: str) -> bool:
    """Bu URL program detayı taşımaz — AI/heuristik active üretmemeli."""
    profile = get_site_profile(url)
    if not profile:
        return False
    parsed = urlparse(url)
    path = (parsed.path or "/").rstrip("/") or "/"
    fragment = (parsed.fragment or "").lower()
    path_l = path.lower()
    domain = profile.domain

    if domain == "foerderportal.wibank.de":
        return True
    if domain == "lfa.de":
        if path in {"/", "/website/de"}:
            return True
        if path_l.endswith("/website/de/index.php"):
            return True
        return False
    if domain == "schleswig-holstein.de":
        return "vi_node" in path_l or "viii_node" in path_l
    if domain == "metropolregion.hamburg.de":
        return path_l.endswith("/foerderfonds") and "projektantraege" not in path_l
    if domain == "umwelt.nrw.de":
        return path in {"/", ""}
    if profile.root_insufficient and path in {"/", ""}:
        return True
    for marker in profile.insufficient_path_markers:
        m = marker.lower()
        if m.startswith("#"):
            if m.lstrip("#") in fragment:
                return True
        elif domain in {"lfa.de", "metropolregion.hamburg.de"}:
            continue
        elif m in path_l:
            return True
    if fragment in {"/public/home", "public/home"}:
        return True
    return False


def build_ai_site_hints(url: str) -> dict:
    """Ollama/Claude user-payload için site_hints bloğu."""
    profile = get_site_profile(url)
    insufficient = url_is_insufficient(url)
    if not profile:
        return {
            "domain": host_of(url) or None,
            "page_kind": "unknown",
            "hints_de": [
                "Fehlende Antragsfrist ≠ unknown.",
                "Nur bei wirklich leerem/irrelevantem Inhalt status=unknown.",
            ],
            "prefer_active_if_described": False,
            "root_insufficient": False,
        }
    return {
        "domain": profile.domain,
        "page_kind": "wrong_url" if insufficient else profile.page_kind,
        "hints_de": list(profile.ai_hints_de),
        "prefer_active_if_described": False if insufficient else profile.prefer_active_if_described,
        "root_insufficient": insufficient,
        "notes": profile.notes or None,
    }


def title_mentioned_in_text(title: str, text: str) -> bool:
    if not title or not text:
        return False
    words = [w for w in title.replace("?", " ").replace("–", " ").split() if len(w) >= 5]
    if not words:
        return False
    hay = text.lower()
    hits = sum(1 for w in words[:6] if w.lower() in hay)
    return hits >= min(2, len(words[:6]))


def page_has_program_substance(text: str) -> bool:
    if not text or len(text) < 120:
        return False
    markers = (
        "förder",
        "antrag",
        "richtlinie",
        "zuschuss",
        "darlehen",
        "bürgschaft",
        "finanzierung",
        "maßnahme",
        "programm",
    )
    low = text.lower()
    return sum(1 for m in markers if m in low) >= 2
