"""Map of Content generation.

For each country we render a single `_MOC/{country}.md` that groups the
country's nodes by type (statute / regulation / guidance / case_law) and lists
their cross-references. Always rebuilt from scratch — it's a view, not state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .vault import MOC_DIR, Note, Vault, wikilink


_TYPE_LABELS = {
    "statute": "Statutes",
    "regulation": "Regulations",
    "guidance": "Guidance",
    "case_law": "Case law",
}

_TYPE_ORDER = ["statute", "regulation", "guidance", "case_law"]


def write_country_moc(vault: Vault, country: str) -> Path:
    notes = [
        n for n in vault.query(country=country)
        if n.status != "quarantine"
    ]
    notes.sort(key=lambda n: ((n.date or "0000"), n.id))

    lines: list[str] = []
    lines.append(f"# {country} — Map of Content")
    lines.append("")
    lines.append(f"_{len(notes)} nodes. Auto-generated; do not edit by hand._")
    lines.append("")

    by_type: dict[str, list[Note]] = {t: [] for t in _TYPE_ORDER}
    for n in notes:
        by_type.setdefault(n.type, []).append(n)

    for t in _TYPE_ORDER:
        group = by_type.get(t, [])
        if not group:
            continue
        lines.append(f"## {_TYPE_LABELS[t]}  ({len(group)})")
        lines.append("")
        for n in group:
            date = f" — {n.date}" if n.date else ""
            reg = f" · *{n.regulator}*" if n.regulator else ""
            status_badge = f" `[{n.status}]`" if n.status != "analyzed" else ""
            lines.append(f"- {wikilink(n.id)} — {n.title}{date}{reg}{status_badge}")
            if n.references:
                # Show outgoing edges so the MOC reads like a graph table of contents.
                lines.append(
                    "  - → "
                    + ", ".join(_truncate_refs(n.references, 10))
                )
        lines.append("")

    target = vault.root / MOC_DIR / f"{country.upper()}.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def write_global_moc(vault: Vault, countries: Iterable[str]) -> Path:
    countries = list(countries)
    lines: list[str] = []
    lines.append("# Crypto LawMap — Global index")
    lines.append("")
    for c in sorted(countries):
        counts = vault.counts_by_status(country=c)
        n_total = sum(v for k, v in counts.items() if k != "quarantine")
        lines.append(
            f"- [[{MOC_DIR}/{c.upper()}|{c.upper()}]] — {n_total} nodes "
            f"(analyzed: {counts.get('analyzed', 0)}, "
            f"quarantine: {counts.get('quarantine', 0)})"
        )
    target = vault.root / MOC_DIR / "INDEX.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def _truncate_refs(refs: list[str], limit: int) -> list[str]:
    if len(refs) <= limit:
        return refs
    return refs[:limit] + [f"… (+{len(refs) - limit} more)"]
