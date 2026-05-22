"""Discovery: seed crypto norms per country, then verify candidate sources.

Two entry points:

  seed_country(country)
      Ask the model (with web_search) for primary crypto norms of a country.
      Output: list of CandidateNorm with title/type/regulator/url/authority.

  verify_candidate(candidate)
      Probe the candidate's URL and score it. Returns (CandidateNorm with
      updated fields, decision: 'verified' | 'quarantine' | 'drop').

  resolve_semantic_suggestion(suggestion)
      For a related-but-uncited suggestion produced by the analyzer, run a
      targeted web search to find a primary source.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from . import confidence as conf
from .anthropic_client import AnthropicClient
from .scraper import HttpScraper

log = logging.getLogger(__name__)


# ---------- Data ----------------------------------------------------------


@dataclass
class CandidateNorm:
    """A norm discovered (seed or semantic), pre- or post-verification."""

    country: str
    jurisdiction: str
    title: str
    type: str  # statute | regulation | guidance | case_law
    regulator: Optional[str] = None
    candidate_url: Optional[str] = None
    source_authority: Optional[str] = None  # set by verify_candidate
    date: Optional[str] = None
    language: Optional[str] = None

    # Verification outputs:
    liveness: Optional[conf.Liveness] = None
    title_score: Optional[float] = None
    confidence: Optional[float] = None
    fetched_text_sample: str = ""  # first ~4 kB, used for title match


# ---------- Country names -------------------------------------------------

# Minimal map; the model fills in the rest in prose.
COUNTRY_NAMES: dict[str, str] = {
    "BR": "Brazil", "US": "United States", "SG": "Singapore",
    "AE": "United Arab Emirates", "GB": "United Kingdom", "JP": "Japan",
    "DE": "Germany", "CH": "Switzerland", "HK": "Hong Kong",
    "KR": "South Korea", "FR": "France", "ES": "Spain", "IT": "Italy",
    "CA": "Canada", "AU": "Australia", "NZ": "New Zealand", "ZA": "South Africa",
    "IN": "India", "MX": "Mexico", "AR": "Argentina", "CO": "Colombia",
    "CL": "Chile", "PT": "Portugal", "NL": "Netherlands", "BE": "Belgium",
    "LU": "Luxembourg", "IE": "Ireland", "MT": "Malta", "INTL": "supranational bodies",
}


# ---------- Prompts -------------------------------------------------------

_SEED_SYSTEM = """You are a legal-research assistant specialized in crypto-asset
regulation. You return STRICT JSON only — no markdown fences, no prose, no
preamble, no trailing commentary. Use the web_search tool to find primary
sources (official gazettes, regulator sites, parliamentary archives) before
deciding what to return."""


_SEED_USER_TEMPLATE = """List the crypto-asset legal norms currently in force in
{country_name} (ISO {country_code}). Include all four types:

  - statute     : laws passed by the legislature
  - regulation  : binding rules issued by financial / monetary regulators
  - guidance    : non-binding interpretive guidance from a regulator
  - case_law    : binding precedents on crypto specifically

Cover at minimum (where they exist): securities, AML/CFT (VASP licensing,
travel rule), payments, tax, central bank stance, consumer protection.

For each norm return ONE object with these fields:

  {{
    "title": "<official title in the original language>",
    "type": "statute | regulation | guidance | case_law",
    "regulator": "<short acronym of the issuing body, or null>",
    "jurisdiction": "<country or sub-jurisdiction name>",
    "candidate_url": "<the most authoritative public URL>",
    "source_authority": "primary | secondary | tertiary",
    "date": "<YYYY-MM-DD if known, else null>",
    "language": "<ISO 639-1 of the original text>"
  }}

Rules:
- Prefer official government / regulator / gazette URLs. Mark them "primary".
- A legal database (eur-lex, etc.) is "secondary". A news article is "tertiary".
- Do NOT include tertiary-only items — drop them entirely.
- Return AT MOST {max_seed} items, ranked by importance.
- Return a JSON ARRAY of objects. Nothing else."""


_SEMANTIC_SYSTEM = _SEED_SYSTEM

_SEMANTIC_USER_TEMPLATE = """Find the most authoritative public URL for the
following norm. Use web_search.

Hint:
  jurisdiction : {jurisdiction}
  title hint   : {title}
  type         : {type}
  regulator    : {regulator}

Return ONE JSON object with these fields:

  {{
    "title": "<corrected official title>",
    "candidate_url": "<best URL>",
    "source_authority": "primary | secondary | tertiary",
    "date": "<YYYY-MM-DD or null>",
    "language": "<ISO 639-1>",
    "regulator": "<acronym or null>"
  }}

If you cannot find a primary source after searching, return:
  {{ "candidate_url": null, "source_authority": "tertiary" }}

Return JSON only. No prose."""


# ---------- Engine --------------------------------------------------------


class DiscoveryEngine:
    def __init__(
        self,
        client: AnthropicClient,
        scraper: HttpScraper,
        *,
        discovery_model: str,
        max_seed_per_country: int = 15,
    ):
        self.client = client
        self.scraper = scraper
        self.discovery_model = discovery_model
        self.max_seed_per_country = max_seed_per_country

    # ------------------------------------------------------------------

    def seed_country(self, country: str) -> list[CandidateNorm]:
        """Ask the model for primary crypto norms in this country."""
        name = COUNTRY_NAMES.get(country.upper(), country)
        user = _SEED_USER_TEMPLATE.format(
            country_name=name,
            country_code=country.upper(),
            max_seed=self.max_seed_per_country,
        )
        log.info("seed_country country=%s name=%s", country, name)
        try:
            data = self.client.message_json(
                model=self.discovery_model,
                system=_SEED_SYSTEM,
                user=user,
                max_tokens=8000,
                use_web_search=True,
            )
        except Exception as e:
            log.warning("seed_country failed country=%s err=%s", country, e)
            return []

        if not isinstance(data, list):
            log.warning("seed_country expected list, got %s", type(data).__name__)
            return []

        out: list[CandidateNorm] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            t = (item.get("type") or "").strip()
            if t not in {"statute", "regulation", "guidance", "case_law"}:
                continue
            url = item.get("candidate_url")
            if not url:
                continue
            authority = (item.get("source_authority") or "").strip() or None
            out.append(
                CandidateNorm(
                    country=country.upper(),
                    jurisdiction=(item.get("jurisdiction") or name),
                    title=(item.get("title") or "").strip(),
                    type=t,
                    regulator=(item.get("regulator") or None),
                    candidate_url=url,
                    source_authority=authority,
                    date=item.get("date"),
                    language=item.get("language"),
                )
            )
        log.info("seed_country country=%s got=%d", country, len(out))
        return out

    # ------------------------------------------------------------------

    def verify_candidate(
        self,
        cand: CandidateNorm,
        *,
        confidence_threshold: float,
    ) -> tuple[CandidateNorm, str]:
        """Probe the URL, score, decide.

        Returns the enriched candidate and one of:
          'verified'   -> ready for SCRAPE
          'quarantine' -> below threshold but kept as a quarantined node
          'drop'       -> not worth storing at all (no URL, or fatal fetch error)
        """
        if not cand.candidate_url:
            return cand, "drop"

        # Re-classify authority from the URL itself (model claims can be wrong).
        authority = conf.classify_authority(cand.candidate_url)
        cand.source_authority = authority

        # Probe.
        liveness, sample = self.scraper.probe(cand.candidate_url)
        cand.liveness = liveness
        cand.fetched_text_sample = sample
        cand.title_score = conf.title_match_score(cand.title, sample)
        cand.confidence = conf.compute_confidence(
            authority=authority,
            liveness=liveness,
            title_score=cand.title_score,
        )

        if not liveness.ok:
            # Completely unreachable URLs are dropped, not even quarantined.
            log.info("verify drop (liveness fail) url=%s status=%s",
                     cand.candidate_url, liveness.status_code)
            return cand, "drop"

        if conf.should_quarantine(cand.confidence, authority, confidence_threshold):
            return cand, "quarantine"
        return cand, "verified"

    # ------------------------------------------------------------------

    def resolve_semantic_suggestion(
        self,
        *,
        country: str,
        jurisdiction: str,
        title: str,
        type_: str,
        regulator: Optional[str],
    ) -> Optional[CandidateNorm]:
        """For a related-but-uncited suggestion, search for a primary source."""
        user = _SEMANTIC_USER_TEMPLATE.format(
            jurisdiction=jurisdiction or country,
            title=title,
            type=type_,
            regulator=regulator or "unknown",
        )
        try:
            data = self.client.message_json(
                model=self.discovery_model,
                system=_SEMANTIC_SYSTEM,
                user=user,
                max_tokens=1500,
                use_web_search=True,
                max_web_searches=3,
            )
        except Exception as e:
            log.warning("resolve_semantic failed title=%r err=%s", title, e)
            return None

        if not isinstance(data, dict):
            return None
        url = data.get("candidate_url")
        if not url:
            return None

        return CandidateNorm(
            country=country.upper(),
            jurisdiction=jurisdiction or country,
            title=(data.get("title") or title).strip(),
            type=type_,
            regulator=(data.get("regulator") or regulator),
            candidate_url=url,
            source_authority=data.get("source_authority"),
            date=data.get("date"),
            language=data.get("language"),
        )
