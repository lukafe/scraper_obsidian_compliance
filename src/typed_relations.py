"""Add typed inline-Dataview relations and the "Fit CertiK" section to notes.

Relations live in the BODY of the note (not the frontmatter), as inline
Dataview fields like `equivalente_a:: [[X]] — porque...`. They become edges
with `tipo_relacao` in the export.

Existing `references` + `ref_types` (citation / semantic) are preserved.

The "## Fit CertiK" section is added at the end of the body, with one
sub-bullet per question:
  - Qual exigência regulatória dispara qual serviço?
  - Em que estágio do funil isso vive?
  - Qual o gap explorável?
  - Quem já está lá?

Idempotent: rerunning checks for existing markers and updates instead of
duplicating.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from . import business_schema as bs
from .vault import Note, Vault, wikilink

log = logging.getLogger(__name__)


# Markers used to find and replace generated sections idempotently.
_TYPED_REL_BEGIN = "<!-- typed-relations: begin -->"
_TYPED_REL_END = "<!-- typed-relations: end -->"
_FIT_CERTIK_BEGIN = "<!-- fit-certik: begin -->"
_FIT_CERTIK_END = "<!-- fit-certik: end -->"


# ---------- Typed-relation inference rules --------------------------------

# Cross-jurisdiction anchor nodes.
MICA_ID = "EU-MICA-2023"
FATF_ID = "INTL-FATFRECS-2025"
TFR_ID = "EU-TFR-2023"
DORA_ID = "EU-DORA-2022"
PROSPECTUS_ID = "EU-PROSPECTUSREG-2017"
DAC8_ID = "EU-DAC8-2023"
GDPR_ID = "EU-GDPR-2016"
HOWEY_ID = "US-HOWEY-1946"
FSB_GSC_ID = "INTL-FSBGSCRECS-2023"
BCBS_CRYPTO_ID = "INTL-BCBSCRYPTOSTANDARD-2022"

# Direct implementations (binding-law transposition).
DERIVADO_DE_ANCHORS = {
    MICA_ID: {"DE", "FR", "IT", "LT", "EU"},
    TFR_ID: {"DE", "FR", "IT", "LT", "EU"},
    DORA_ID: {"DE", "FR", "IT", "LT", "EU"},
    PROSPECTUS_ID: {"DE", "FR", "IT", "LT", "EU"},
    DAC8_ID: {"DE", "FR", "IT", "LT", "EU"},
    GDPR_ID: {"DE", "FR", "IT", "LT", "EU"},
}

# Soft inspiration (non-binding influence — works across all countries).
INSPIRADO_EM_ANCHORS = {
    FATF_ID: None,            # FATF inspires every jurisdiction
    FSB_GSC_ID: None,         # FSB stablecoin recommendations
    BCBS_CRYPTO_ID: None,     # Basel crypto-asset standard
    MICA_ID: {"BR", "GB", "AE", "US", "SG", "JP", "HK", "CH", "KR", "AR", "TR",
              "ZA", "NG", "MX", "UY", "BM", "CA"},  # non-EU referencing MiCA
    HOWEY_ID: {"BR", "GB", "AE", "SG", "JP", "HK", "CH", "KR", "AR", "CA"},  # security test exported
}


def infer_typed_relations(note: Note, vault: Vault) -> list[tuple[str, str, str]]:
    """Derive typed relations for a note.

    Returns list of (tipo_relacao, target_id, justificativa).
    Tipos: derivado_de | inspirado_em | equivalente_a | regulado_por |
    exige_servico | referencia_cruzada | precede_deadline.
    """
    out: list[tuple[str, str, str]] = []
    extra = note.extra
    refs_str = " ".join(note.references)

    # 1) derivado_de: country-level norms that legally transpose a supranational
    #    anchor (MiCA/TFR/DORA/Prospectus/DAC8/GDPR within EU/EEA).
    for anchor, eligible in DERIVADO_DE_ANCHORS.items():
        if anchor in refs_str and (eligible is None or note.country in eligible):
            label_map = {
                MICA_ID: "MiCA (UE 2023/1114)",
                TFR_ID: "TFR (UE 2023/1113)",
                DORA_ID: "DORA (UE 2022/2554)",
                PROSPECTUS_ID: "EU Prospectus Regulation 2017/1129",
                DAC8_ID: "DAC8 (UE 2023/2226)",
                GDPR_ID: "GDPR (UE 2016/679)",
            }
            out.append((
                "derivado_de", anchor,
                f"transposição/implementação nacional de {label_map.get(anchor, anchor)}",
            ))

    # 2) inspirado_em: non-binding influence (FATF for all; MiCA/Howey for non-EU
    #    when explicitly cited).
    for anchor, eligible in INSPIRADO_EM_ANCHORS.items():
        if anchor not in refs_str:
            continue
        if eligible is not None and note.country not in eligible:
            continue
        label_map = {
            FATF_ID: "FATF Recommendations (R.15 / Travel Rule)",
            FSB_GSC_ID: "FSB stablecoin/crypto recommendations",
            BCBS_CRYPTO_ID: "Basel Committee crypto-asset standard",
            MICA_ID: "MiCA (referência não vinculante fora da UE)",
            HOWEY_ID: "teste de Howey (US securities test)",
        }
        out.append((
            "inspirado_em", anchor,
            f"alinhamento com {label_map.get(anchor, anchor)}",
        ))

    # 3) referencia_cruzada: explicit citations in body (from ref_types).
    for ref_id, ref_type in note.ref_types.items():
        if ref_type == "citation":
            out.append((
                "referencia_cruzada", ref_id,
                "citação explícita no corpo da norma",
            ))

    # 4) regulado_por: regulator string from frontmatter.
    if note.regulator:
        out.append((
            "regulado_por", note.regulator,
            "regulador competente designado pela norma",
        ))

    # 5) exige_servico: services derived from boolean triggers.
    for svc in extra.get("servicos_certik_aplicaveis") or []:
        triggers = [
            k for k, s in bs.SERVICE_TRIGGERS.items()
            if s == svc and extra.get(k) is True
        ]
        why = f"trigger(s) frontmatter: {', '.join(triggers)}" if triggers else "exigência da norma dispara este serviço"
        out.append(("exige_servico", svc, why))

    # 6) precede_deadline: if a future deadline is set.
    if extra.get("deadline_principal"):
        out.append((
            "precede_deadline", str(extra["deadline_principal"]),
            f"data de vigência -> deadline em {extra['deadline_principal']}",
        ))

    # Dedup (preserve order, keep first occurrence).
    seen = set()
    unique = []
    for tipo, target, just in out:
        key = (tipo, target)
        if key in seen:
            continue
        seen.add(key)
        unique.append((tipo, target, just))
    return unique


def format_typed_relations_section(
    relations: list[tuple[str, str, str]],
) -> str:
    """Render the inline-Dataview block for the body."""
    if not relations:
        return ""
    lines = [_TYPED_REL_BEGIN, "## Typed relations"]
    for tipo, target, justificativa in relations:
        # target may be a vault id (wikilink) or a plain string
        is_wikilink_candidate = (
            re.match(r"^[A-Z]{2,4}-", target)
            and target == target.upper().replace(" ", "")
        )
        rendered_target = wikilink(target) if is_wikilink_candidate else target
        lines.append(f"- `{tipo}:: {rendered_target}` — {justificativa}")
    lines.append(_TYPED_REL_END)
    return "\n".join(lines) + "\n"


def build_fit_certik_section(note: Note) -> str:
    """Produce the 'Fit CertiK' section for a note."""
    extra = note.extra
    services = extra.get("servicos_certik_aplicaveis") or []
    gap = extra.get("gap_ou_ambiguidade")
    regime = extra.get("regime") or "desconhecido"
    status = extra.get("status_regulatorio") or "desconhecido"

    # Funnel stage — derived from status
    funnel = {
        "em_consulta": "EARLY — mercado abrindo, oportunidade pra entrar nas mesas técnicas",
        "proposto": "EARLY — projeto em tramitação",
        "em_implementacao": "MID — regra está sendo operacionalizada, demanda emergente",
        "vigente": "LATE — mercado regulado e maduro, venda por substituição/expansão",
        "desconhecido": "indeterminado",
    }.get(status, "indeterminado")

    services_block = (
        ", ".join(f"`{s}`" for s in services) if services else "_(nenhum trigger explícito)_"
    )

    triggers_explained = []
    for k, svc in bs.SERVICE_TRIGGERS.items():
        if extra.get(k) is True:
            triggers_explained.append(f"`{k}` → `{svc}`")
    triggers_block = ("\n".join(f"  - {t}" for t in triggers_explained)
                      if triggers_explained
                      else "  - _(sem triggers booleanos explícitos no frontmatter)_")

    competidores = extra.get("competidores_ativos") or []
    competidores_block = (
        ", ".join(competidores) if competidores
        else "_(nenhum competidor mapeado nesta norma — ver overview do país)_"
    )

    return (
        _FIT_CERTIK_BEGIN + "\n"
        "## Fit CertiK\n\n"
        f"**Serviços disparados:** {services_block}\n\n"
        f"**Triggers:**\n{triggers_block}\n\n"
        f"**Estágio do funil:** {funnel} (regime: `{regime}`, status: `{status}`)\n\n"
        f"**Gap explorável:** {gap or '_(não identificado / preencher após análise LLM)_'}\n\n"
        f"**Competidores ativos nesta norma:** {competidores_block}\n"
        + _FIT_CERTIK_END + "\n"
    )


def _replace_section(body: str, begin: str, end: str, new_content: str) -> str:
    """Replace `begin..end` block in body with new_content (or insert at end)."""
    if begin in body and end in body:
        return re.sub(
            re.escape(begin) + r".*?" + re.escape(end) + r"\n?",
            new_content,
            body,
            count=1,
            flags=re.DOTALL,
        )
    # Append at end with separator
    suffix = "\n\n---\n\n" + new_content if body.strip() else new_content
    return body + suffix


def write_note_extensions(note: Note, vault: Vault) -> bool:
    """Apply typed-relations block and Fit-CertiK section to the note body.

    Idempotent: existing blocks are replaced in place.
    Returns True if the note body was modified.
    """
    relations = infer_typed_relations(note, vault)
    rel_section = format_typed_relations_section(relations)
    fit_section = build_fit_certik_section(note)

    old_body = note.body or ""
    new_body = old_body
    if rel_section:
        new_body = _replace_section(new_body, _TYPED_REL_BEGIN, _TYPED_REL_END, rel_section)
    new_body = _replace_section(new_body, _FIT_CERTIK_BEGIN, _FIT_CERTIK_END, fit_section)

    if new_body != old_body:
        note.body = new_body
        vault.write(note)
        return True
    return False
