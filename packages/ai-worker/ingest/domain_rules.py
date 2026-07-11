"""Domain-bazlı Playwright kuralları — site_profiles üzerinden.

Geriye uyumluluk: browser_client DomainRule API'sini kullanmaya devam eder.
AI ipuçları için ai.site_profiles kullanın.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from ai.site_profiles import SITE_PROFILES, get_site_profile, host_of


@dataclass(frozen=True)
class DomainRule:
    domain: str
    wait_until: str = "domcontentloaded"
    use_inner_text_fallback: bool = False
    try_lowercase_on_404: bool = False
    known_working_subpaths: tuple[str, ...] = ()
    notes: str = ""


def _profile_to_rule(profile) -> DomainRule:
    return DomainRule(
        domain=profile.domain,
        wait_until=profile.wait_until,
        use_inner_text_fallback=profile.use_inner_text_fallback,
        try_lowercase_on_404=profile.try_lowercase_on_404,
        known_working_subpaths=profile.known_working_subpaths,
        notes=profile.notes,
    )


DOMAIN_RULES: dict[str, DomainRule] = {
    domain: _profile_to_rule(profile) for domain, profile in SITE_PROFILES.items()
}

# Beklenen kurumsal redirect hedefleri (hijack değil)
KNOWN_OK_REDIRECT_HOSTS = frozenset(
    {
        "bmbfsfj.bund.de",
        "bayernportal.de",
        "login.aufbaubank.de",
        "landwirtschaft.hessen.de",
        "www.landwirtschaft.hessen.de",
    }
)

# Açık hijack / reklam domain imzaları
HIJACK_HOST_MARKERS = (
    "travelerzdeal",
    "deal.",
    "coupon",
    "affiliate",
    "click.",
    "track.",
)


def get_rule_for_url(url: str) -> DomainRule | None:
    profile = get_site_profile(url)
    if profile:
        return _profile_to_rule(profile)
    return None


def is_suspicious_redirect(original_url: str, final_url: str) -> bool:
    """Domain hijack / alakasız reklam redirect tespiti."""
    orig = host_of(original_url)
    final = host_of(final_url)
    if not final or orig == final:
        return False
    if final in KNOWN_OK_REDIRECT_HOSTS:
        return False
    if final.endswith("." + orig) or orig.endswith("." + final):
        return False
    if any(m in final for m in HIJACK_HOST_MARKERS):
        return True
    # Hijack-notlu domainler: tamamen farklı host = şüpheli
    rule = get_rule_for_url(original_url)
    if rule and "Hijack" in (rule.notes or "") and final != orig:
        return True
    return False


def expand_url_variants(url: str) -> list[str]:
    """Domain kurallarına göre denenecek URL listesi."""
    parsed = urlparse(url)
    variants: list[str] = [url]
    rule = get_rule_for_url(url)

    if parsed.netloc == "lfa.de":
        variants.append(urlunparse(parsed._replace(netloc="www.lfa.de")))
    if parsed.netloc and not parsed.netloc.startswith("www."):
        variants.append(urlunparse(parsed._replace(netloc="www." + parsed.netloc)))
    if "bmfsfj.de" in parsed.netloc:
        variants.append(
            url.replace("bmfsfj.de", "bmbfsfj.bund.de").replace("www.bmfsfj", "www.bmbfsfj")
        )

    if rule and rule.try_lowercase_on_404 and parsed.path:
        lower_path = parsed.path.lower()
        if lower_path != parsed.path:
            variants.append(urlunparse(parsed._replace(path=lower_path)))

    if rule and rule.known_working_subpaths:
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc if parsed.netloc.startswith("www.") else f"www.{host_of(url)}"
        # foerderportal → wibank ana domain alt yolları ayrı
        if "foerderportal.wibank.de" in host_of(url):
            for sub in ("/",):
                variants.append(f"{scheme}://www.wibank.de{sub}")
        else:
            for sub in rule.known_working_subpaths:
                variants.append(f"{scheme}://{netloc}{sub}")

    # Metropolregion Förderfonds teaser → Antrag-Unterseite
    if "metropolregion.hamburg.de" in host_of(url) and "foerderfonds" in (parsed.path or ""):
        if "projektantraege" not in (parsed.path or ""):
            variants.append(
                "https://metropolregion.hamburg.de/ueber-uns/foerderfonds/"
                "projektantraege-und-richtlinien-8498"
            )

    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out
