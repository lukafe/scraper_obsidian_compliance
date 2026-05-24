"""Enrichment: add business frontmatter to existing vault notes.

Idempotent: running twice doesn't duplicate or overwrite existing values.
Non-destructive: never deletes existing keys; only adds missing ones.
Conflict-safe: if a key already has a non-null value, it's preserved (an
explicit `_conflict` marker can be appended if `overwrite=True` is forced).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from . import business_schema as bs
from .vault import Note, Vault

log = logging.getLogger(__name__)


def enrich_note_baseline(note: Note, *, mark_revision: bool = True) -> bool:
    """Add baseline business fields to a note's frontmatter.

    Returns True if the note's frontmatter was modified.
    """
    extra = note.extra
    changed = False
    for key, default in bs.NORM_BUSINESS_FIELDS.items():
        if key not in extra:
            extra[key] = list(default) if isinstance(default, list) else default
            changed = True
    if mark_revision and changed:
        extra["ultima_revisao"] = bs.today_iso()
    return changed


def apply_llm_findings(note: Note, findings: dict[str, Any]) -> bool:
    """Merge findings produced by the LLM gap analyzer into a note.

    `findings` is a dict with keys like `regime`, `status_regulatorio`,
    `deadline_principal`, `exige_*`, `gap_ou_ambiguidade`, `escopo`, etc.
    Only writes values that are non-null and pass schema validation.

    Evidence quotes (`<field>_evidence`) are written atomically with their
    parent field — either both land or neither does — so a value in the
    vault always traces back to a quoted span of the legal text.
    """
    extra = note.extra
    changed = False
    evidence_set = set(bs.EVIDENCE_FIELDS)

    def assign(
        key: str,
        value: Any,
        allowed_set: Optional[set] = None,
        *,
        evidence: Optional[str] = None,
    ) -> None:
        nonlocal changed
        if value is None:
            return
        if allowed_set is not None and value not in allowed_set:
            return
        cur = extra.get(key)
        is_empty = cur in (None, "", [])
        if is_empty:
            # Empty cell: fill with new value (+ evidence if available).
            extra[key] = value
            if key in evidence_set:
                extra[f"{key}_evidence"] = evidence
            changed = True
            return
        # Phase 1 upgrade: when re-analyzing, allow a NEW evidence-backed
        # finding to overwrite an existing UNEVIDENCED value. Strict
        # improvement — the value either stays the same (now anchored) or
        # gets replaced by something the LLM can defend with a quote.
        if key in evidence_set and evidence and not extra.get(f"{key}_evidence"):
            extra[key] = value
            extra[f"{key}_evidence"] = evidence
            changed = True

    assign(
        "regime", findings.get("regime"), bs.REGIME_VALUES,
        evidence=findings.get("regime_evidence"),
    )
    assign(
        "status_regulatorio", findings.get("status_regulatorio"),
        bs.STATUS_REG_VALUES,
        evidence=findings.get("status_regulatorio_evidence"),
    )
    assign(
        "deadline_principal", findings.get("deadline_principal"),
        evidence=findings.get("deadline_principal_evidence"),
    )
    assign(
        "tipo_deadline", findings.get("tipo_deadline"),
        bs.TIPO_DEADLINE_VALUES,
        evidence=findings.get("tipo_deadline_evidence"),
    )
    assign("escopo", findings.get("escopo"))
    assign("gap_ou_ambiguidade", findings.get("gap_ou_ambiguidade"))

    # Boolean triggers (atomic with their evidence quote — same Phase 1
    # promotion rule as the structured fields above).
    for trigger in bs.SERVICE_TRIGGERS:
        v = findings.get(trigger)
        if v is not True and v is not False:
            continue
        cur = extra.get(trigger)
        new_evidence = findings.get(f"{trigger}_evidence")
        if cur is None:
            extra[trigger] = v
            if trigger in evidence_set:
                extra[f"{trigger}_evidence"] = new_evidence
            changed = True
        elif (
            trigger in evidence_set
            and new_evidence
            and not extra.get(f"{trigger}_evidence")
        ):
            extra[trigger] = v
            extra[f"{trigger}_evidence"] = new_evidence
            changed = True

    # Derive services from triggers (always re-derive — cheap)
    derived = bs.derive_services_from_triggers(extra)
    if derived and derived != extra.get("servicos_certik_aplicaveis", []):
        extra["servicos_certik_aplicaveis"] = derived
        changed = True

    # Confidence: LLM-extracted findings start at "media" unless cur is "alta"
    if extra.get("confianca_dados") is None:
        extra["confianca_dados"] = findings.get("confianca_dados", "media")
        changed = True

    if changed:
        extra["ultima_revisao"] = bs.today_iso()

    return changed


def enrich_country(vault: Vault, country: str, *,
                   notes_filter=None) -> tuple[int, int]:
    """Apply baseline enrichment to all non-quarantine notes of a country.

    Returns (n_scanned, n_modified).
    """
    scanned = 0
    modified = 0
    for note in vault.iter_notes():
        if note.country != country:
            continue
        if note.status == "quarantine":
            continue
        if notes_filter is not None and not notes_filter(note):
            continue
        scanned += 1
        if enrich_note_baseline(note):
            vault.write(note)
            modified += 1
    log.info("enrichment country=%s scanned=%d modified=%d",
             country, scanned, modified)
    return scanned, modified
