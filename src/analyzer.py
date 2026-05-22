"""Analyzer: turn a scraped norm body into two lists of references.

Two engines run on the same model call but are treated very differently:

  citations: explicit references to other norms ("amends Law X", "art. Y of
             Regulation Z", citations of treaties/recommendations). Deterministic
             and safe — these are facts in the text. Promoted directly.

  related:   semantically related but uncited. Probabilistic — these go through
             discovery.resolve_semantic_suggestion() to find a primary source,
             then through verification, and are quarantined unless they clear
             the confidence threshold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from .anthropic_client import AnthropicClient

log = logging.getLogger(__name__)


# ---------- Output dataclasses -------------------------------------------


@dataclass
class Citation:
    """An explicit reference found in the body of a norm."""
    title: str                          # English display title
    country: str                        # ISO alpha-2 ("INTL" for supranational)
    jurisdiction: str
    type: str                           # statute | regulation | guidance | case_law | treaty
    title_original: Optional[str] = None
    short_label: Optional[str] = None
    regulator: Optional[str] = None
    candidate_url: Optional[str] = None
    date: Optional[str] = None


@dataclass
class Related:
    """A semantically related-but-uncited norm suggested by the model."""
    title: str                          # English display title
    country: str
    jurisdiction: str
    type: str
    title_original: Optional[str] = None
    short_label: Optional[str] = None
    regulator: Optional[str] = None
    reason: str = ""                    # one short sentence on why it's relevant


@dataclass
class Analysis:
    citations: list[Citation]
    related: list[Related]


# ---------- Prompts ------------------------------------------------------


_ANALYZE_SYSTEM = """You analyze legal texts about crypto-asset regulation. You
return STRICT JSON only — no markdown fences, no prose, no preamble. Be
precise: only return what is in the text (for citations) or clearly adjacent
(for related)."""


_ANALYZE_USER_TEMPLATE = """The following is the body of a crypto regulation
from {country_name} ({country_code}).

Source metadata:
  id           : {note_id}
  type         : {note_type}
  jurisdiction : {jurisdiction}
  regulator    : {regulator}
  title        : {title}

Return a JSON object with exactly TWO fields. ALL titles in `title_en` MUST
be in English (the engineers who read this graph speak only English).

{{
  "citations": [
    // ANY norm explicitly referenced in the text — laws, regulations,
    // treaties, FATF recommendations, court decisions, EU directives, etc.
    // ONE object per distinct norm; deduplicate.
    {{
      "title_en": "<title in ENGLISH — official English version where one exists, otherwise faithful translation; keep numeric identifiers, e.g. 'Law No. 14,478 of 2022'>",
      "title_original": "<title in the original language; null only if the cited norm was natively in English>",
      "short_label": "<6-20 char compact identifier, e.g. 'LAW14478', 'MICA', 'AMLD5'>",
      "country": "<ISO alpha-2; use 'INTL' for supranational like FATF/BIS/FSB>",
      "jurisdiction": "<jurisdiction name in English>",
      "type": "statute | regulation | guidance | case_law | treaty",
      "regulator": "<acronym or null>",
      "candidate_url": "<URL if you are confident, else null>",
      "date": "<YYYY-MM-DD or YYYY or null>"
    }}
  ],
  "related": [
    // Norms NOT cited but clearly relevant and adjacent (e.g. the AML law
    // this regulation implements, the EU directive being transposed, a
    // standard from FATF that informs the article). Max 8 items.
    {{
      "title_en": "<best-known title in ENGLISH>",
      "title_original": "<title in the original language or null>",
      "short_label": "<compact identifier or null>",
      "country": "<ISO alpha-2 or INTL>",
      "jurisdiction": "<jurisdiction name in English>",
      "type": "statute | regulation | guidance | case_law",
      "regulator": "<acronym or null>",
      "reason": "<one short sentence in English>"
    }}
  ]
}}

Rules:
- For citations: only include what the text actually references. If it just
  says "applicable AML legislation" without naming the law, do NOT include it.
- Use the country code of the cited norm's jurisdiction (e.g. the body text
  is Brazilian but it cites a FATF recommendation -> country: "INTL").
- All English fields MUST be in English. Do not mix languages.
- Return JSON only.

--- BEGIN BODY ---
{body}
--- END BODY ---"""


# Truncate the body sent to the analyzer; very long codes are unnecessary.
_ANALYZE_BODY_LIMIT = 80_000


# ---------- Engine -------------------------------------------------------


class AnalyzerEngine:
    def __init__(self, client: AnthropicClient, *, model: str):
        self.client = client
        self.model = model

    def analyze(
        self,
        *,
        note_id: str,
        country: str,
        country_name: str,
        jurisdiction: str,
        regulator: Optional[str],
        title: str,
        note_type: str,
        body: str,
    ) -> Analysis:
        if not body or not body.strip():
            return Analysis(citations=[], related=[])

        body_chunk = body[:_ANALYZE_BODY_LIMIT]
        user = _ANALYZE_USER_TEMPLATE.format(
            note_id=note_id,
            country_code=country,
            country_name=country_name,
            jurisdiction=jurisdiction,
            regulator=regulator or "unknown",
            title=title,
            note_type=note_type,
            body=body_chunk,
        )
        try:
            data = self.client.message_json(
                model=self.model,
                system=_ANALYZE_SYSTEM,
                user=user,
                max_tokens=4000,
            )
        except Exception as e:
            log.warning("analyze failed note_id=%s err=%s", note_id, e)
            return Analysis(citations=[], related=[])

        if not isinstance(data, dict):
            log.warning("analyze expected dict, got %s", type(data).__name__)
            return Analysis(citations=[], related=[])

        citations = _parse_citations(data.get("citations") or [])
        related = _parse_related(data.get("related") or [])
        log.info(
            "analyze note_id=%s citations=%d related=%d",
            note_id, len(citations), len(related),
        )
        return Analysis(citations=citations, related=related)


# ---------- Parsers ------------------------------------------------------

_VALID_TYPES_CIT = {"statute", "regulation", "guidance", "case_law", "treaty"}
_VALID_TYPES_REL = {"statute", "regulation", "guidance", "case_law"}


def _norm_country(c: Any) -> str:
    s = str(c or "").strip().upper()
    if not s:
        return "INTL"
    return s[:4]  # tolerate "INTL"


def _parse_citations(items: Any) -> list[Citation]:
    out: list[Citation] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        t = (it.get("type") or "").strip()
        if t not in _VALID_TYPES_CIT:
            continue
        # Accept both new ("title_en") and old ("title") shapes.
        title = (it.get("title_en") or it.get("title") or "").strip()
        if not title:
            continue
        # We normalize "treaty" -> "guidance" for vault purposes (treaties
        # behave like guidance — supranational, non-self-executing in most
        # jurisdictions). Keeps the type-set small.
        node_type = "guidance" if t == "treaty" else t
        out.append(Citation(
            title=title,
            title_original=(it.get("title_original") or None),
            short_label=(it.get("short_label") or None),
            country=_norm_country(it.get("country")),
            jurisdiction=(it.get("jurisdiction") or "").strip() or "Unknown",
            type=node_type,
            regulator=(it.get("regulator") or None),
            candidate_url=(it.get("candidate_url") or None),
            date=(it.get("date") or None),
        ))
    return out


def _parse_related(items: Any) -> list[Related]:
    out: list[Related] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        t = (it.get("type") or "").strip()
        if t not in _VALID_TYPES_REL:
            continue
        title = (it.get("title_en") or it.get("title") or "").strip()
        if not title:
            continue
        out.append(Related(
            title=title,
            title_original=(it.get("title_original") or None),
            short_label=(it.get("short_label") or None),
            country=_norm_country(it.get("country")),
            jurisdiction=(it.get("jurisdiction") or "").strip() or "Unknown",
            type=t,
            regulator=(it.get("regulator") or None),
            reason=(it.get("reason") or "").strip(),
        ))
    return out
