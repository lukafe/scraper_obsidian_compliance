"""LLM-driven gap analyzer.

For each scraped/analyzed norm, asks the model (Gemini Pro or Claude) to
extract structured business signals from the body:

- regime: licenciamento | registro | proibicao | em_consulta | sem_regra
- status_regulatorio: vigente | em_implementacao | em_consulta | proposto
- deadline_principal (YYYY-MM-DD or null)
- tipo_deadline: licenciamento | transicao | sunset | consulta_publica | go_live
- exige_* (booleans): auditoria_tecnica, proof_of_reserves, pentest, kyt_aml,
  seguranca_custodia, formal_verification, certificacao_independente
- escopo: 1-2 sentences summary of what the norm regulates
- gap_ou_ambiguidade: 1-2 sentences on regulatory ambiguity / certifier opportunity

Phase 1 — evidence trail: every non-null structured field must come with a
verbatim quote (`<field>_evidence`) copied straight from the body. Quotes
that are not exact substrings of the input body are stripped, demoting the
field back to null. That makes every claim traceable to the legal text.

Strict JSON output, with explicit null for unknowns. NEVER invent.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from . import business_schema as bs

log = logging.getLogger(__name__)


# Fields that MUST carry an `<field>_evidence` quote when non-null. Free-form
# fields (escopo / gap_ou_ambiguidade) are themselves the evidence so they
# are exempt.
_EVIDENCE_REQUIRED_FIELDS = (
    "regime",
    "status_regulatorio",
    "deadline_principal",
    "tipo_deadline",
    "exige_auditoria_tecnica",
    "exige_proof_of_reserves",
    "exige_pentest",
    "exige_kyt_aml",
    "exige_seguranca_custodia",
    "exige_formal_verification",
    "exige_certificacao_independente",
)


_SYSTEM = """You analyze legal texts about crypto-asset regulation to extract STRUCTURED
business signals for a regulatory-opportunity scoring algorithm.

CRITICAL RULES:
- Return STRICT JSON only — no markdown fences, no prose, no preamble.
- Use null for any field you cannot determine with CONFIDENCE from the text.
- NEVER invent dates, deadlines, requirements or facts. A null answer is
  better than a plausible guess. The system has a `confianca_dados` field
  to surface uncertainty.
- Booleans are TRUE only if the text EXPLICITLY requires the activity; FALSE
  if the text explicitly excludes it; null if the text is silent.
- Dates: ISO YYYY-MM-DD only. If only a year or month is known, use null.
- Free-form fields (`escopo`, `gap_ou_ambiguidade`) must be ≤ 2 short sentences
  in English.
- For every non-null structured field you MUST also return a companion
  `<field>_evidence` key whose value is a 30-400 character substring copied
  VERBATIM from the body — the smallest fragment that justifies the call.
  The reviewer must be able to ctrl-F that exact string in the source.
  If you cannot quote the text, return null for both the field and its
  evidence. Substitutions, summaries or paraphrases are forbidden."""


_USER_TEMPLATE = """Norm metadata:
  id           : {note_id}
  country      : {country}
  jurisdiction : {jurisdiction}
  type         : {note_type}
  regulator    : {regulator}
  date         : {date}
  title        : {title}

Return ONE JSON object with EXACTLY these keys (use null for unknown):

{{
  "regime": "licenciamento | registro | proibicao | em_consulta | sem_regra | null",
  "regime_evidence": "verbatim quote from the body (30-400 chars) or null",

  "status_regulatorio": "vigente | em_implementacao | em_consulta | proposto | null",
  "status_regulatorio_evidence": "verbatim quote or null",

  "deadline_principal": "YYYY-MM-DD or null",
  "deadline_principal_evidence": "verbatim quote or null",

  "tipo_deadline": "licenciamento | transicao | sunset | consulta_publica | go_live | reporte_periodico | null",
  "tipo_deadline_evidence": "verbatim quote or null",

  "exige_auditoria_tecnica": "true | false | null",
  "exige_auditoria_tecnica_evidence": "verbatim quote or null",

  "exige_proof_of_reserves": "true | false | null",
  "exige_proof_of_reserves_evidence": "verbatim quote or null",

  "exige_pentest": "true | false | null",
  "exige_pentest_evidence": "verbatim quote or null",

  "exige_kyt_aml": "true | false | null",
  "exige_kyt_aml_evidence": "verbatim quote or null",

  "exige_seguranca_custodia": "true | false | null",
  "exige_seguranca_custodia_evidence": "verbatim quote or null",

  "exige_formal_verification": "true | false | null",
  "exige_formal_verification_evidence": "verbatim quote or null",

  "exige_certificacao_independente": "true | false | null",
  "exige_certificacao_independente_evidence": "verbatim quote or null",

  "escopo": "1-2 short sentences in English on what the norm regulates, or null",
  "gap_ou_ambiguidade": "1-2 sentences in English on regulatory ambiguity or certifier opportunity, or null"
}}

Guidance:
- 'regime' = how is the activity controlled?
  licenciamento = requires prior authorization (most common for VASPs/CASPs)
  registro     = registration-only (no full authorization)
  proibicao    = explicit ban
  em_consulta  = still in public consultation
  sem_regra    = explicitly silent/unregulated for the matter
- 'exige_auditoria_tecnica' = the norm requires a technical security audit of
  smart contracts / IT systems (broad sense — independent technical review).
- 'exige_proof_of_reserves' = reserves attestation (typical for stablecoins).
- 'exige_pentest' = explicit penetration testing or red-teaming requirement.
- 'exige_kyt_aml' = transaction monitoring, sanctions screening, Travel Rule.
- 'exige_seguranca_custodia' = security controls for custody of client assets
  (segregation, cold storage, access controls).
- 'exige_formal_verification' = mathematical/formal verification of code.
- 'exige_certificacao_independente' = certification by an independent third
  party as a licensing precondition (Brazil's IN 701 is the canonical example).
- 'gap_ou_ambiguidade' = where is the rule unclear, missing a technical
  standard, or open to interpretation that an independent certifier could
  fill? Concrete and short. Null if no clear gap.
- EVIDENCE QUOTES: pick the shortest sentence (or single clause) from the
  body that, on its own, supports the call. If the source is non-English,
  quote the original language — do not translate.

--- BEGIN BODY ---
{body}
--- END BODY ---"""


_BODY_LIMIT = 60_000  # chars
_EVIDENCE_MIN = 20    # chars — guards against single-word "evidence"
_EVIDENCE_MAX = 600   # chars — generous ceiling, prompt asks for 30-400


def analyze_norm_body(
    client,
    *,
    model: str,
    note_id: str,
    country: str,
    jurisdiction: str,
    note_type: str,
    regulator: Optional[str],
    date_str: Optional[str],
    title: str,
    body: str,
    thinking_budget: int = 4000,
    max_output_tokens: int = 6000,
) -> Optional[dict[str, Any]]:
    """Run the LLM analyzer on one norm body. Returns the parsed JSON or None."""
    if not body or not body.strip():
        return None

    truncated_body = body[:_BODY_LIMIT]
    user = _USER_TEMPLATE.format(
        note_id=note_id,
        country=country,
        jurisdiction=jurisdiction,
        note_type=note_type,
        regulator=regulator or "unknown",
        date=date_str or "unknown",
        title=title,
        body=truncated_body,
    )

    is_gemini = (
        hasattr(client, "cfg")
        and client.cfg.__class__.__name__ == "GeminiConfig"
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "system": _SYSTEM,
        "user": user,
        "max_tokens": max_output_tokens,
    }
    if is_gemini:
        kwargs["thinking_budget"] = thinking_budget

    try:
        data = client.message_json(**kwargs)
    except Exception as e:
        log.warning("gap_analyzer failed note_id=%s err=%s", note_id, e)
        return None

    if not isinstance(data, dict):
        log.warning("gap_analyzer returned non-dict for %s", note_id)
        return None

    return _normalize_findings(data, body=truncated_body, note_id=note_id)


def _normalize_findings(
    d: dict[str, Any],
    *,
    body: str = "",
    note_id: str = "",
) -> dict[str, Any]:
    """Normalize the JSON output:
    - string 'true'/'false'/'null' -> python types
    - drop unknown keys
    - validate every <field>_evidence is a verbatim substring of `body`;
      if not, demote the matching field back to null.
    """
    allowed = {
        "regime", "status_regulatorio", "deadline_principal", "tipo_deadline",
        "exige_auditoria_tecnica", "exige_proof_of_reserves", "exige_pentest",
        "exige_kyt_aml", "exige_seguranca_custodia",
        "exige_formal_verification", "exige_certificacao_independente",
        "escopo", "gap_ou_ambiguidade",
    }
    evidence_keys = {f"{f}_evidence" for f in _EVIDENCE_REQUIRED_FIELDS}

    out: dict[str, Any] = {}
    for k, v in d.items():
        if k not in allowed and k not in evidence_keys:
            continue
        if isinstance(v, str):
            sv = v.strip()
            low = sv.lower()
            if low in ("null", "none", "n/a", "unknown", "", "desconhecido"):
                out[k] = None
                continue
            if k in allowed and low == "true":
                out[k] = True
                continue
            if k in allowed and low == "false":
                out[k] = False
                continue
            out[k] = sv
            continue
        out[k] = v

    if body:
        _enforce_evidence(out, body=body, note_id=note_id)
    return out


def _enforce_evidence(
    out: dict[str, Any],
    *,
    body: str,
    note_id: str,
) -> None:
    """For each field requiring evidence, verify the quote is verbatim. If not,
    demote the field back to None and log the offense — caller treats the
    result identically to a 'model wasn't confident' answer.
    """
    for field in _EVIDENCE_REQUIRED_FIELDS:
        evidence_key = f"{field}_evidence"
        value = out.get(field)
        quote = out.get(evidence_key)

        if value is None:
            out[evidence_key] = None
            continue

        if not isinstance(quote, str) or not quote.strip():
            log.info(
                "gap_analyzer: missing evidence for %s/%s — demoting to null",
                note_id, field,
            )
            out[field] = None
            out[evidence_key] = None
            continue

        cleaned = quote.strip()
        if len(cleaned) < _EVIDENCE_MIN:
            log.info(
                "gap_analyzer: evidence too short for %s/%s (%d chars) — demoting",
                note_id, field, len(cleaned),
            )
            out[field] = None
            out[evidence_key] = None
            continue
        if len(cleaned) > _EVIDENCE_MAX:
            cleaned = cleaned[:_EVIDENCE_MAX]

        if not _quote_in_body(cleaned, body):
            log.info(
                "gap_analyzer: evidence not verbatim for %s/%s — demoting",
                note_id, field,
            )
            out[field] = None
            out[evidence_key] = None
            continue

        out[evidence_key] = cleaned


def _quote_in_body(quote: str, body: str) -> bool:
    """Forgiving substring check: collapses internal whitespace so a model
    that joined two lines with a single space still validates against a body
    that contained the original newline. Case-sensitive — legal text is.
    """
    norm_body = " ".join(body.split())
    norm_quote = " ".join(quote.split())
    if not norm_quote:
        return False
    return norm_quote in norm_body
