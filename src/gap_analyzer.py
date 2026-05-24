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

Strict JSON output, with explicit null for unknowns. NEVER invent.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from . import business_schema as bs

log = logging.getLogger(__name__)


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
  in English."""


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
  "status_regulatorio": "vigente | em_implementacao | em_consulta | proposto | null",
  "deadline_principal": "YYYY-MM-DD or null",
  "tipo_deadline": "licenciamento | transicao | sunset | consulta_publica | go_live | reporte_periodico | null",
  "exige_auditoria_tecnica": "true | false | null",
  "exige_proof_of_reserves": "true | false | null",
  "exige_pentest": "true | false | null",
  "exige_kyt_aml": "true | false | null",
  "exige_seguranca_custodia": "true | false | null",
  "exige_formal_verification": "true | false | null",
  "exige_certificacao_independente": "true | false | null",
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

--- BEGIN BODY ---
{body}
--- END BODY ---"""


_BODY_LIMIT = 60_000  # chars


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
    max_output_tokens: int = 4000,
) -> Optional[dict[str, Any]]:
    """Run the LLM analyzer on one norm body. Returns the parsed JSON or None."""
    if not body or not body.strip():
        return None

    user = _USER_TEMPLATE.format(
        note_id=note_id,
        country=country,
        jurisdiction=jurisdiction,
        note_type=note_type,
        regulator=regulator or "unknown",
        date=date_str or "unknown",
        title=title,
        body=body[:_BODY_LIMIT],
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

    return _normalize_findings(data)


def _normalize_findings(d: dict[str, Any]) -> dict[str, Any]:
    """Normalize the JSON output:
    - string 'true'/'false'/'null' -> python types
    - drop unknown keys
    """
    allowed = {
        "regime", "status_regulatorio", "deadline_principal", "tipo_deadline",
        "exige_auditoria_tecnica", "exige_proof_of_reserves", "exige_pentest",
        "exige_kyt_aml", "exige_seguranca_custodia",
        "exige_formal_verification", "exige_certificacao_independente",
        "escopo", "gap_ou_ambiguidade",
    }
    out: dict[str, Any] = {}
    for k, v in d.items():
        if k not in allowed:
            continue
        # Normalize string-encoded values
        if isinstance(v, str):
            sv = v.strip().lower()
            if sv in ("null", "none", "n/a", "unknown", "", "desconhecido"):
                out[k] = None
                continue
            if sv == "true":
                out[k] = True
                continue
            if sv == "false":
                out[k] = False
                continue
        out[k] = v
    return out
