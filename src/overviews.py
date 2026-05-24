"""Per-country jurisdiction overview generator.

Produces one note per country at `vault/_business/jur/{CC}.md`. Each
overview aggregates the country's underlying norms into a single
business-readable node — this is what the scoring algorithm reads.

Aggregation rules:
- `exige_*` flags: TRUE if ANY underlying norm has it TRUE.
- `servicos_certik_aplicaveis`: union of all triggered services.
- `frameworks_aplicaveis`: top-N most-cited (by inlinks) non-quarantine norms.
- `deadline_principal`: earliest non-null `deadline_principal` >= today.
- `regime`, `status_regulatorio`, `maturidade_mercado`: filled with
  `desconhecido` baseline; can be edited manually or overridden by an LLM
  pass on the overview later.

Non-destructive: if an overview note already exists with manually-edited
fields, those are preserved (we use upsert semantics).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import frontmatter

from . import business_schema as bs
from . import coverage as cov
from .vault import Note, Vault, wikilink

log = logging.getLogger(__name__)


_BUSINESS_DIR = "_business"
_JUR_DIR = "jur"
_BUSINESS_TIPO_JURISDICAO = "jurisdicao"


def _overview_path(vault: Vault, country: str) -> Path:
    return vault.root / _BUSINESS_DIR / _JUR_DIR / f"{country.upper()}.md"


def _infer_maturidade_mercado(covered: set[str]) -> str:
    """Phase 4 — text-grounded maturity. Maps the set of regulatory
    dimensions actually covered by this jurisdiction's norms to the
    legacy `MATURIDADE_VALUES` vocabulary. See `coverage.maturity_from_coverage`.
    """
    return cov.maturity_from_coverage(covered)


def _aggregate_country(vault: Vault, country: str) -> dict:
    """Compute aggregates from all non-quarantine norms of `country`."""
    norms = [n for n in vault.iter_notes()
             if n.country == country.upper() and n.status != "quarantine"]
    n_total = len(norms)
    n_analyzed = sum(1 for n in norms if n.status == "analyzed")
    n_quarantine = sum(
        1 for n in vault.iter_notes()
        if n.country == country.upper() and n.status == "quarantine"
    )

    # Service trigger aggregation: TRUE if any underlying norm has it TRUE.
    exige = {k: False for k in bs.SERVICE_TRIGGERS}
    services: set[str] = set()
    regulators_seen: Counter[str] = Counter()
    earliest_deadline: Optional[str] = None
    today = date.today()

    for n in norms:
        for k in bs.SERVICE_TRIGGERS:
            if n.extra.get(k) is True:
                exige[k] = True
        for svc in n.extra.get("servicos_certik_aplicaveis") or []:
            services.add(svc)
        if n.regulator:
            regulators_seen[n.regulator] += 1

        d = n.extra.get("deadline_principal")
        if isinstance(d, str) and len(d) >= 10:
            try:
                dt = datetime.fromisoformat(d[:10]).date()
                if dt >= today and (
                    earliest_deadline is None
                    or dt < datetime.fromisoformat(earliest_deadline).date()
                ):
                    earliest_deadline = d[:10]
            except Exception:
                pass

    # Top frameworks (by inlinks within the country + supranational anchors).
    inlinks: Counter[str] = Counter()
    for n in vault.iter_notes():
        for ref in n.references:
            m = re.match(r"\[\[([^\]\|]+)", ref.strip())
            if m:
                inlinks[m.group(1).strip()] += 1
    country_norms_ids = {n.id for n in norms}
    top_frameworks_pairs = sorted(
        [(nid, c) for nid, c in inlinks.items() if nid in country_norms_ids],
        key=lambda x: -x[1],
    )[:8]
    top_frameworks = [pair[0] for pair in top_frameworks_pairs]

    # Principal regulator: the most-frequent in this country's norms.
    regulador_principal = (regulators_seen.most_common(1)[0][0]
                           if regulators_seen else None)
    reguladores_secundarios = [r for r, _ in regulators_seen.most_common(6)[1:]
                               if r != regulador_principal]

    # Earliest anchor year (oldest analyzed-status norm) — kept for context.
    earliest_anchor_year = None
    for n in norms:
        if n.status != "analyzed":
            continue
        if isinstance(n.date, str) and len(n.date) >= 4:
            try:
                y = int(n.date[:4])
                if earliest_anchor_year is None or y < earliest_anchor_year:
                    earliest_anchor_year = y
            except Exception:
                pass

    # Phase 4 — text-grounded coverage and maturity.
    covered = cov.aggregate_coverage(n.extra for n in norms)
    maturidade = _infer_maturidade_mercado(covered)

    return {
        "n_total": n_total,
        "n_analyzed": n_analyzed,
        "n_quarantine": n_quarantine,
        "exige": exige,
        "services": sorted(services),
        "regulador_principal": regulador_principal,
        "reguladores_secundarios": reguladores_secundarios,
        "earliest_deadline": earliest_deadline,
        "top_frameworks": top_frameworks,
        "maturidade_inferred": maturidade,
        "earliest_anchor_year": earliest_anchor_year,
        "cobertura": sorted(covered),
    }


def upsert_overview(vault: Vault, country: str) -> Path:
    """Create or update the country overview note.

    Preserves manually-edited fields (only fills missing ones).
    """
    country = country.upper()
    agg = _aggregate_country(vault, country)
    path = _overview_path(vault, country)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing frontmatter if present (preserve manual edits).
    if path.exists():
        post = frontmatter.load(path)
        fm = dict(post.metadata)
        body = post.content
    else:
        fm = {}
        body = ""

    def ensure(key: str, value) -> None:
        # Only fill if absent or None / empty.
        if fm.get(key) in (None, "", []):
            fm[key] = value

    ensure("tipo", _BUSINESS_TIPO_JURISDICAO)
    ensure("pais", bs.COUNTRY_NAMES.get(country, country))
    ensure("iso", country)
    ensure("regiao", bs.REGIONS.get(country, "desconhecido"))
    ensure("regime", "desconhecido")
    ensure("status_regulatorio", "desconhecido")
    ensure("forca_relacionamento_certik", "desconhecido")
    ensure("oportunidade_score", None)
    ensure("confianca_dados", "media")
    ensure("fontes", [])
    ensure("competidores_ativos", [])
    ensure("tipo_deadline", None)
    # Phase 4 — maturity is now text-grounded; recompute every run so
    # changes to the underlying norms (or to the coverage detector) are
    # reflected immediately. The earlier "preserve manual edits" carve-out
    # is dropped — the field is now algorithmic, not editorial.
    fm["maturidade_mercado"] = agg["maturidade_inferred"]
    fm["cobertura_regulatoria"] = agg["cobertura"]

    # Always refresh aggregates (they're computed, not human-edited).
    fm["regulador_principal"] = agg["regulador_principal"]
    fm["reguladores_secundarios"] = agg["reguladores_secundarios"]
    fm["deadline_principal"] = agg["earliest_deadline"]
    fm["frameworks_aplicaveis"] = [wikilink(x) for x in agg["top_frameworks"]]
    fm["servicos_certik_aplicaveis"] = agg["services"]
    for k, v in agg["exige"].items():
        fm[k] = v
    fm["n_normas_total"] = agg["n_total"]
    fm["n_normas_analyzed"] = agg["n_analyzed"]
    fm["n_quarantine"] = agg["n_quarantine"]
    fm["ultima_revisao"] = bs.today_iso()

    # Body: deterministic auto-generated summary (replace if present).
    body = _render_body(country, agg, fm)
    post = frontmatter.Post(body, **fm)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


def _render_body(country: str, agg: dict, fm: dict) -> str:
    name = bs.COUNTRY_NAMES.get(country, country)
    services = agg["services"] or ["_(nenhum trigger ativado nas normas atuais)_"]
    deadline = agg["earliest_deadline"] or "_(nenhum deadline futuro identificado)_"
    frameworks = (
        "\n".join(f"  - [[{nid}]]" for nid in agg["top_frameworks"])
        if agg["top_frameworks"]
        else "  - _(nenhum hub identificado)_"
    )
    reguladores = (
        f"**{agg['regulador_principal']}**"
        + (f" + secundários: {', '.join(agg['reguladores_secundarios'])}"
           if agg["reguladores_secundarios"] else "")
        if agg["regulador_principal"] else "_(não identificado)_"
    )
    return (
        f"# {name} — Jurisdiction Overview\n\n"
        f"_Auto-gerado a partir das {agg['n_total']} normas no vault. "
        f"Última revisão: {fm.get('ultima_revisao')}._\n\n"
        f"## Indicadores rápidos\n\n"
        f"- **Normas no vault:** {agg['n_total']} "
        f"(analyzed: {agg['n_analyzed']}, quarantine: {agg['n_quarantine']})\n"
        f"- **Reguladores:** {reguladores}\n"
        f"- **Deadline mais próximo:** {deadline}\n"
        f"- **Serviços CertiK disparados:** "
        f"{', '.join(f'`{s}`' for s in services)}\n\n"
        f"## Frameworks-âncora\n\n{frameworks}\n\n"
        f"## Notas\n\n"
        f"- Campos `regime`, `status_regulatorio`, `maturidade_mercado` "
        f"vêm como `desconhecido` por padrão — preencher manualmente ou via "
        f"análise LLM ad-hoc.\n"
        f"- `forca_relacionamento_certik` e `competidores_ativos` requerem "
        f"input humano (não inferíveis das normas).\n"
    )
