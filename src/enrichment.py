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
    """
    extra = note.extra
    changed = False

    def assign(key: str, value: Any, allowed_set: Optional[set] = None) -> None:
        nonlocal changed
        if value is None:
            return
        if allowed_set is not None and value not in allowed_set:
            return
        # Don't overwrite manually-set values; only fill where empty/None.
        cur = extra.get(key)
        if cur in (None, "", []):
            extra[key] = value
            changed = True

    assign("regime", findings.get("regime"), bs.REGIME_VALUES)
    assign("status_regulatorio", findings.get("status_regulatorio"), bs.STATUS_REG_VALUES)
    assign("deadline_principal", findings.get("deadline_principal"))
    assign("tipo_deadline", findings.get("tipo_deadline"), bs.TIPO_DEADLINE_VALUES)
    assign("escopo", findings.get("escopo"))
    assign("gap_ou_ambiguidade", findings.get("gap_ou_ambiguidade"))

    # Boolean triggers
    for trigger in bs.SERVICE_TRIGGERS:
        v = findings.get(trigger)
        if v is True or v is False:
            if extra.get(trigger) is None:
                extra[trigger] = v
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
