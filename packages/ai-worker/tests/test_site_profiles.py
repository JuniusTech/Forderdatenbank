"""Site profile + Ollama postprocess testleri."""

from ai.page_extractor import PageExtractResult, _apply_site_postprocess, _build_user_payload
from ai.site_profiles import build_ai_site_hints, get_site_profile, url_is_insufficient
from ingest.domain_rules import expand_url_variants, get_rule_for_url


def test_site_hints_injected_into_payload():
    system, payload = _build_user_payload(
        page_text="Förderprogramm Text",
        program_title="Testprogramm",
        page_url="https://www.schleswig-holstein.de/DE/fachinhalte/J/justizvollzug/bildungsmassnahmen.html",
        reference=None,
        text_limit=500,
    )
    assert "site_hints" in payload
    assert payload["site_hints"]["domain"] == "schleswig-holstein.de"
    assert payload["site_hints"]["prefer_active_if_described"] is True
    assert "site_hints" in system or "Domain-Charakteristik" in system


def test_vi_node_is_insufficient():
    assert url_is_insufficient(
        "https://www.schleswig-holstein.de/DE/Landesregierung/VI/vi_node.html"
    )
    assert not url_is_insufficient(
        "https://www.schleswig-holstein.de/DE/fachinhalte/J/justizvollzug/bildungsmassnahmen.html"
    )


def test_lfa_root_insufficient_hint():
    hints = build_ai_site_hints("https://www.lfa.de/")
    assert hints["root_insufficient"] is True
    hints_product = build_ai_site_hints(
        "https://www.lfa.de/website/de/foerderangebote/finanzierung/risikoentlastungen/index.php"
    )
    assert hints_product["root_insufficient"] is False


def test_wibank_portal_always_insufficient():
    assert url_is_insufficient("https://foerderportal.wibank.de/site/#/public/home")
    assert get_site_profile("https://foerderportal.wibank.de/site/#/public/home").domain == (
        "foerderportal.wibank.de"
    )


def test_metropolregion_expands_antrag_subpage():
    variants = expand_url_variants("https://metropolregion.hamburg.de/foerderfonds/")
    assert any("projektantraege-und-richtlinien-8498" in v for v in variants)


def test_postprocess_upgrades_unknown_when_program_described():
    text = (
        "Das Förderprogramm Aktion 100 unterstützt Unternehmen in NRW mit Zuschuss. "
        "Antragstellung ist über das Portal möglich. Finanzierung und Maßnahme "
        "werden in der Richtlinie beschrieben. Zuwendung und Bewilligung erfolgen "
        "nach Prüfung. Das Programm läuft ohne Antragsstopp."
    )
    raw = PageExtractResult(
        status="unknown",
        reason="keine Frist",
        confidence="low",
        method="ollama",
    )
    out = _apply_site_postprocess(
        raw,
        page_text=text,
        program_title="Aktion 100 NRW",
        page_url="https://www.mags.nrw/aktion-100",
    )
    assert out.status == "active"
    assert out.confidence == "medium"
    assert "site" in out.method


def test_postprocess_keeps_unknown_on_lfa_root():
    raw = PageExtractResult(
        status="active",
        reason="Startseite",
        confidence="medium",
        method="ollama",
    )
    out = _apply_site_postprocess(
        raw,
        page_text="Wir fördern Bayern. Menü Navigation Kontakt.",
        program_title="Energiekredit",
        page_url="https://www.lfa.de/",
    )
    assert out.status == "unknown"


def test_postprocess_keeps_unknown_on_vi_node_even_if_active():
    raw = PageExtractResult(status="active", reason="news", confidence="medium", method="ollama")
    out = _apply_site_postprocess(
        raw,
        page_text="Pressemitteilungen Finanzministerium News Feed Veranstaltungen",
        program_title="Bürgschaften des Landes",
        page_url="https://www.schleswig-holstein.de/DE/Landesregierung/VI/vi_node.html",
    )
    assert out.status == "unknown"


def test_bb_h_forces_inner_text_profile():
    profile = get_site_profile("https://bb-h.de/angebot/klassische-buergschaft/")
    assert profile is not None
    assert profile.use_inner_text_fallback is True
    rule = get_rule_for_url("https://bb-h.de/angebot/klassische-buergschaft/")
    assert rule is not None
    assert rule.use_inner_text_fallback is True


def test_domain_rules_still_resolve_from_profiles():
    rule = get_rule_for_url("https://www.nbank.de/foerderung/x")
    assert rule is not None
    assert rule.wait_until == "networkidle"
    assert get_site_profile("https://www.nbank.de/x") is not None


def test_regioaktiv_root_insufficient_and_title_resolve():
    from ingest.domain_rules import resolve_program_url

    assert url_is_insufficient("https://regioaktiv.sachsen-anhalt.de/")
    assert not url_is_insufficient(
        "https://regioaktiv.sachsen-anhalt.de/ueber-regio-aktiv/foerderbereiche/famico"
    )
    mapped = resolve_program_url(
        "https://regioaktiv.sachsen-anhalt.de/",
        "„REGIO AKTIV“ – Familien stärken – Perspektiven eröffnen (FAMICO)",
    )
    assert mapped and mapped.endswith("/famico")
    mapped_ae = resolve_program_url(
        "https://regioaktiv.sachsen-anhalt.de/",
        "REGIO AKTIV – Aktive Eingliederung (AE)",
    )
    assert mapped_ae and mapped_ae.endswith("/aktive-eingliederung")


def test_pdf_url_helper():
    from ingest.pdf_text import is_pdf_url

    assert is_pdf_url("https://projekttraeger.dlr.de/media/x/Alter_und_Krebs.pdf")
    assert not is_pdf_url("https://projekttraeger.dlr.de/media/x/page.html")
