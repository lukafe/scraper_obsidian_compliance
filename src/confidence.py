"""Confidence scoring.

A node's `confidence` is the geometric blend of three signals:

  authority  : where the URL lives (gov/regulator vs aggregator vs media)
  liveness   : the URL actually returns content (HTTP 200, non-empty)
  title_match: the claimed title is consistent with the fetched page

Below `confidence_threshold` -> quarantine (the auto-policing mechanism).
Tertiary sources are *never* promoted into the graph, regardless of liveness or
title match — they can only be leads to find a primary source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from rapidfuzz import fuzz

# ---------- Authority -----------------------------------------------------

# Domain substrings that mark a primary (official) source.
PRIMARY_DOMAINS: tuple[str, ...] = (
    # Executive / federal gov gazettes
    ".gov", ".gob.", ".gouv.", ".gov.br", ".gov.uk", ".gov.sg", ".gov.ae",
    ".gov.au", ".gov.hk", ".gov.kr", ".gov.za", ".gov.in", ".gov.mx",
    ".admin.ch", ".bund.de", ".europa.eu", "eur-lex.europa.eu",
    # Brazilian legislative + judicial + prosecutorial branches
    ".leg.br", ".jus.br", ".mp.br", "camara.leg.br", "senado.leg.br",
    "stf.jus.br", "stj.jus.br", "tse.jus.br",
    "planalto.gov.br", "bcb.gov.br", "cvm.gov.br", "in.gov.br", "receita.fazenda.gov.br",
    # US
    "congress.gov", "federalregister.gov", "sec.gov", "treasury.gov",
    "cftc.gov", "fincen.gov", "occ.treas.gov", "irs.gov", "supremecourt.gov",
    "uscourts.gov",
    # UK
    "legislation.gov.uk", "fca.org.uk", "bankofengland.co.uk", "parliament.uk",
    # Singapore
    "mas.gov.sg", "sso.agc.gov.sg", "supremecourt.gov.sg",
    # Japan
    "japaneselawtranslation.go.jp", "fsa.go.jp", ".go.jp", "courts.go.jp",
    # Germany
    "bafin.de", "gesetze-im-internet.de", "bundestag.de",
    # Switzerland
    "finma.ch", "fedlex.admin.ch", "parlament.ch",
    # Hong Kong
    "sfc.hk", "hkma.gov.hk", "legislation.gov.hk",
    # South Korea
    "fsc.go.kr", "law.go.kr", ".go.kr",
    # UAE
    "centralbank.ae", "vara.ae", "sca.gov.ae",
    # Supranational standard-setters
    "fatf-gafi.org", "bis.org", "fsb.org", "iosco.org", "imf.org",
    "oecd.org", "worldbank.org", "un.org",
)

# Aggregators / law databases — usually accurate but second-hand.
SECONDARY_DOMAINS: tuple[str, ...] = (
    "wipo.int", "law.cornell.edu", "westlaw.com", "lexology.com",
    "global-regulation.com", "lexisnexis.com", "jusbrasil.com.br",
    "conjur.com.br", "migalhas.com.br",
)


def classify_authority(url: Optional[str]) -> str:
    """Return 'primary' | 'secondary' | 'tertiary' based on the URL."""
    if not url:
        return "tertiary"
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return "tertiary"
    if not host:
        return "tertiary"
    for needle in PRIMARY_DOMAINS:
        if needle in host:
            return "primary"
    for needle in SECONDARY_DOMAINS:
        if needle in host:
            return "secondary"
    return "tertiary"


_AUTHORITY_WEIGHT = {
    "primary": 1.00,
    "secondary": 0.65,
    "tertiary": 0.25,
}

# ---------- Title match ---------------------------------------------------


def title_match_score(claimed_title: str, page_text: str) -> float:
    """Fuzzy match the claimed title against the first chunk of the page.

    Returns 0.0–1.0. Uses partial-ratio (longest near-match) which is
    forgiving of formatting noise around the title in the page text.
    """
    if not claimed_title or not page_text:
        return 0.0
    head = page_text[:4000]  # title almost always appears near the top
    score = fuzz.partial_ratio(claimed_title.lower(), head.lower())
    return max(0.0, min(1.0, score / 100.0))


# ---------- Liveness ------------------------------------------------------


@dataclass
class Liveness:
    """Outcome of a HEAD/GET probe."""

    ok: bool
    status_code: Optional[int]
    content_length: int = 0
    final_url: Optional[str] = None

    @property
    def score(self) -> float:
        if not self.ok:
            return 0.0
        # Penalize very short pages — usually error pages with 200.
        if self.content_length < 500:
            return 0.4
        return 1.0


# ---------- Combined confidence ------------------------------------------


def compute_confidence(
    *,
    authority: str,
    liveness: Liveness,
    title_score: float,
) -> float:
    """Blend the three signals into a single 0-1 confidence."""
    a = _AUTHORITY_WEIGHT.get(authority, 0.25)
    l = liveness.score
    t = max(0.0, min(1.0, title_score))
    # Weighted product so a zero in any factor pulls hard. 50/30/20.
    blended = (a ** 0.50) * (l ** 0.30) * (t ** 0.20)
    return round(blended, 3)


def should_quarantine(
    confidence: float,
    authority: str,
    threshold: float,
) -> bool:
    """Apply the quarantine policy.

    Tertiary sources are *always* quarantined regardless of score.
    """
    if authority == "tertiary":
        return True
    return confidence < threshold
