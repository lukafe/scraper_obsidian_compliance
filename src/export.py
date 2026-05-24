"""Export the vault as flat tables + a graph JSON for the scoring algorithm.

Three output files (under vault/_export/):

  jurisdicoes.csv  — one row per country (the per-country overview notes).
                     Includes raw features (`maturidade_mercado`, etc.) and
                     derived numerics (`urgencia_deadline_dias`,
                     `n_servicos`, `n_competidores`, `inlinks`, `outlinks`).

  normas.csv       — one row per legal norm (every non-quarantine note in
                     the country folders + EU/INTL anchors). All business
                     frontmatter flattened.

  grafo.json       — { "nodes": [...], "edges": [...] } — full graph
                     including overview nodes, norms, and typed edges.

The exporter never computes the final score — it surfaces raw features for
the downstream algorithm.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import frontmatter

from . import business_schema as bs
from .vault import Note, Vault, wikilink

log = logging.getLogger(__name__)

_EXPORT_DIR = "_export"
_BUSINESS_DIR = "_business"


def _today() -> date:
    return date.today()


def _days_until(iso_str: Optional[str]) -> Optional[int]:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str)[:10]).date()
        return (dt - _today()).days
    except Exception:
        return None


def _read_overview_notes(vault: Vault) -> list[tuple[str, dict, str]]:
    """Return [(iso, frontmatter, body), ...] for each /_business/jur/*.md."""
    out = []
    jur_dir = vault.root / _BUSINESS_DIR / "jur"
    if not jur_dir.exists():
        return out
    for p in sorted(jur_dir.glob("*.md")):
        post = frontmatter.load(p)
        iso = p.stem
        out.append((iso, dict(post.metadata), post.content))
    return out


def _norms_for(vault: Vault, country: Optional[str] = None,
               include_quarantine: bool = True) -> list[Note]:
    """Iterate norm notes (excludes overview notes)."""
    out = []
    for n in vault.iter_notes():
        if country and n.country != country:
            continue
        if n.status == "quarantine" and not include_quarantine:
            continue
        out.append(n)
    return out


def _inlinks_index(vault: Vault) -> Counter:
    inlinks: Counter[str] = Counter()
    for n in vault.iter_notes():
        for ref in n.references:
            m = re.match(r"\[\[([^\]\|]+)", ref.strip())
            if m:
                inlinks[m.group(1).strip()] += 1
    return inlinks


# ---------- jurisdicoes.csv ----------------------------------------------


JURISDICAO_COLUMNS = [
    "iso", "pais", "regiao",
    "regulador_principal", "reguladores_secundarios_csv",
    "regime", "status_regulatorio", "maturidade_mercado",
    "deadline_principal", "tipo_deadline", "urgencia_deadline_dias",
    "exige_auditoria_tecnica", "exige_proof_of_reserves",
    "exige_pentest", "exige_kyt_aml", "exige_seguranca_custodia",
    "exige_formal_verification", "exige_certificacao_independente",
    "servicos_certik_aplicaveis_csv", "n_servicos",
    "competidores_ativos_csv", "n_competidores",
    "forca_relacionamento_certik",
    "n_normas_total", "n_normas_analyzed", "n_quarantine",
    "frameworks_aplicaveis_csv",
    "inlinks_grafo", "outlinks_grafo",
    "confianca_dados", "ultima_revisao",
]


def export_jurisdicoes_csv(vault: Vault, path: Path,
                           inlinks: Counter, outlinks: Counter) -> int:
    overviews = _read_overview_notes(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    n_written = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=JURISDICAO_COLUMNS)
        w.writeheader()
        for iso, fm, _body in overviews:
            services = fm.get("servicos_certik_aplicaveis") or []
            competidores = fm.get("competidores_ativos") or []
            secundarios = fm.get("reguladores_secundarios") or []
            frameworks = fm.get("frameworks_aplicaveis") or []
            row = {
                "iso": iso,
                "pais": fm.get("pais"),
                "regiao": fm.get("regiao"),
                "regulador_principal": fm.get("regulador_principal"),
                "reguladores_secundarios_csv": " | ".join(secundarios),
                "regime": fm.get("regime"),
                "status_regulatorio": fm.get("status_regulatorio"),
                "maturidade_mercado": fm.get("maturidade_mercado"),
                "deadline_principal": fm.get("deadline_principal"),
                "tipo_deadline": fm.get("tipo_deadline"),
                "urgencia_deadline_dias": _days_until(fm.get("deadline_principal")),
                **{k: fm.get(k) for k in bs.SERVICE_TRIGGERS},
                "servicos_certik_aplicaveis_csv": " | ".join(services),
                "n_servicos": len(services),
                "competidores_ativos_csv": " | ".join(competidores),
                "n_competidores": len(competidores),
                "forca_relacionamento_certik": fm.get("forca_relacionamento_certik"),
                "n_normas_total": fm.get("n_normas_total"),
                "n_normas_analyzed": fm.get("n_normas_analyzed"),
                "n_quarantine": fm.get("n_quarantine"),
                "frameworks_aplicaveis_csv": " | ".join(str(f) for f in frameworks),
                "inlinks_grafo": inlinks.get(iso, 0),
                "outlinks_grafo": outlinks.get(iso, 0),
                "confianca_dados": fm.get("confianca_dados"),
                "ultima_revisao": fm.get("ultima_revisao"),
            }
            w.writerow(row)
            n_written += 1
    return n_written


# ---------- normas.csv ----------------------------------------------------


NORMA_COLUMNS = [
    "id", "country", "jurisdiction", "type", "title", "title_original",
    "regulator", "date", "status", "discovered_via", "cycle",
    "source_url", "source_authority", "confidence",
    "regime", "status_regulatorio",
    "deadline_principal", "tipo_deadline", "urgencia_deadline_dias",
    "exige_auditoria_tecnica", "exige_proof_of_reserves",
    "exige_pentest", "exige_kyt_aml", "exige_seguranca_custodia",
    "exige_formal_verification", "exige_certificacao_independente",
    "servicos_certik_aplicaveis_csv", "n_servicos",
    "escopo", "gap_ou_ambiguidade",
    # Phase 1 — evidence trail: verbatim quotes from the source body.
    *[f"{f}_evidence" for f in bs.EVIDENCE_FIELDS],
    "n_inlinks", "n_outlinks",
    "confianca_dados", "ultima_revisao", "in_quarantine",
]


def export_normas_csv(vault: Vault, path: Path, inlinks: Counter) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_written = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=NORMA_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for n in _norms_for(vault, include_quarantine=True):
            extra = n.extra
            services = extra.get("servicos_certik_aplicaveis") or []
            row = {
                "id": n.id,
                "country": n.country,
                "jurisdiction": n.jurisdiction,
                "type": n.type,
                "title": n.title,
                "title_original": n.title_original,
                "regulator": n.regulator,
                "date": n.date,
                "status": n.status,
                "discovered_via": n.discovered_via,
                "cycle": n.cycle,
                "source_url": n.source_url,
                "source_authority": n.source_authority,
                "confidence": n.confidence,
                "regime": extra.get("regime"),
                "status_regulatorio": extra.get("status_regulatorio"),
                "deadline_principal": extra.get("deadline_principal"),
                "tipo_deadline": extra.get("tipo_deadline"),
                "urgencia_deadline_dias": _days_until(extra.get("deadline_principal")),
                **{k: extra.get(k) for k in bs.SERVICE_TRIGGERS},
                "servicos_certik_aplicaveis_csv": " | ".join(services),
                "n_servicos": len(services),
                "escopo": extra.get("escopo"),
                "gap_ou_ambiguidade": extra.get("gap_ou_ambiguidade"),
                **{
                    f"{f}_evidence": extra.get(f"{f}_evidence")
                    for f in bs.EVIDENCE_FIELDS
                },
                "n_inlinks": inlinks.get(n.id, 0),
                "n_outlinks": len(n.references),
                "confianca_dados": extra.get("confianca_dados"),
                "ultima_revisao": extra.get("ultima_revisao"),
                "in_quarantine": n.status == "quarantine",
            }
            w.writerow(row)
            n_written += 1
    return n_written


# ---------- grafo.json ---------------------------------------------------

# Edge weights: rough heuristic — typed/justified edges weigh more.
EDGE_WEIGHTS = {
    "citation": 0.9,             # explicit citation in body
    "semantic": 0.5,             # model-suggested similarity
    "derivado_de": 1.0,          # legally implements / transposes
    "equivalente_a": 0.9,        # same regulatory scope, different jurisdiction
    "regulado_por": 0.7,         # regulator association
    "exige_servico": 0.8,        # norm fires CertiK service
    "referencia_cruzada": 0.85,  # mutual reference between two norms
    "precede_deadline": 0.6,     # deadline cascade
    "compete_com": 0.5,          # competitor on the same opportunity
    "aplica_se_a": 0.7,          # jurisdiction → norm
    "default": 0.5,
}


def _extract_inline_typed_relations(body: str) -> list[tuple[str, str]]:
    """Parse inline Dataview fields like `tipo:: [[X]]` from a body."""
    out = []
    if not body:
        return out
    for m in re.finditer(
        r"`?([a-z_]+)::\s*(?:\[\[([^\]\|]+))?",
        body,
    ):
        tipo = m.group(1).strip()
        target = (m.group(2) or "").strip()
        if not target:
            continue
        out.append((tipo, target))
    return out


def export_grafo_json(vault: Vault, path: Path, inlinks: Counter) -> tuple[int, int]:
    """Write the graph JSON. Returns (n_nodes, n_edges)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids_seen: set[str] = set()

    # 1) Overview nodes
    for iso, fm, body in _read_overview_notes(vault):
        node = {
            "id": iso,
            "kind": "jurisdicao",
            "label": fm.get("pais") or iso,
            "regiao": fm.get("regiao"),
            "regulador_principal": fm.get("regulador_principal"),
            "regime": fm.get("regime"),
            "status_regulatorio": fm.get("status_regulatorio"),
            "deadline_principal": fm.get("deadline_principal"),
            "urgencia_deadline_dias": _days_until(fm.get("deadline_principal")),
            "n_normas_total": fm.get("n_normas_total"),
            "servicos_certik_aplicaveis": fm.get("servicos_certik_aplicaveis"),
            "competidores_ativos": fm.get("competidores_ativos"),
            "forca_relacionamento_certik": fm.get("forca_relacionamento_certik"),
            "maturidade_mercado": fm.get("maturidade_mercado"),
            "confianca_dados": fm.get("confianca_dados"),
        }
        nodes.append(node)
        node_ids_seen.add(iso)

        # aplica_se_a edges (jurisdicao -> norm)
        for fw in fm.get("frameworks_aplicaveis") or []:
            target = re.sub(r"^\[\[|\]\]$", "", str(fw))
            target = target.split("|")[0].strip()
            if target:
                edges.append({
                    "source": iso,
                    "target": target,
                    "tipo_relacao": "aplica_se_a",
                    "peso": EDGE_WEIGHTS["aplica_se_a"],
                    "justificativa": f"framework-âncora de {iso}",
                })

    # 2) Norm nodes
    for n in _norms_for(vault, include_quarantine=True):
        if n.id in node_ids_seen:
            continue
        extra = n.extra
        node = {
            "id": n.id,
            "kind": "lei",
            "label": n.title[:80],
            "country": n.country,
            "type": n.type,
            "regulator": n.regulator,
            "date": n.date,
            "source_authority": n.source_authority,
            "confidence": n.confidence,
            "status": n.status,
            "regime": extra.get("regime"),
            "status_regulatorio": extra.get("status_regulatorio"),
            "deadline_principal": extra.get("deadline_principal"),
            "urgencia_deadline_dias": _days_until(extra.get("deadline_principal")),
            "servicos_certik_aplicaveis": extra.get("servicos_certik_aplicaveis"),
            "n_inlinks": inlinks.get(n.id, 0),
            "in_quarantine": n.status == "quarantine",
            "confianca_dados": extra.get("confianca_dados"),
        }
        nodes.append(node)
        node_ids_seen.add(n.id)

        # 2a) existing typed edges from ref_types
        for ref_id, ref_type in n.ref_types.items():
            edges.append({
                "source": n.id,
                "target": ref_id,
                "tipo_relacao": ref_type,
                "peso": EDGE_WEIGHTS.get(ref_type, EDGE_WEIGHTS["default"]),
                "justificativa": (
                    "citação explícita encontrada no corpo da norma"
                    if ref_type == "citation"
                    else "sugestão semântica do analisador"
                ),
            })

        # 2b) inline Dataview typed relations from the body
        for tipo, target in _extract_inline_typed_relations(n.body or ""):
            edges.append({
                "source": n.id,
                "target": target,
                "tipo_relacao": tipo,
                "peso": EDGE_WEIGHTS.get(tipo, EDGE_WEIGHTS["default"]),
                "justificativa": "relação tipada extraída do body (inline Dataview)",
            })

    # 3) jurisdicao → jurisdicao soft links via shared regulators (MiCA cluster)
    #    Not implemented in v1 — algorithm can derive from `aplica_se_a` paths.

    payload = {"nodes": nodes, "edges": edges, "generated": bs.today_iso()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return len(nodes), len(edges)


# ---------- Driver -------------------------------------------------------


def export_all(vault: Vault, countries: Optional[Iterable[str]] = None) -> dict:
    """Run all exporters. Returns counts."""
    export_dir = vault.root / _EXPORT_DIR
    export_dir.mkdir(parents=True, exist_ok=True)

    inlinks = _inlinks_index(vault)
    outlinks: Counter[str] = Counter()
    for n in vault.iter_notes():
        outlinks[n.country] += len(n.references)

    counts = {}
    counts["jurisdicoes_rows"] = export_jurisdicoes_csv(
        vault, export_dir / "jurisdicoes.csv", inlinks, outlinks,
    )
    counts["normas_rows"] = export_normas_csv(
        vault, export_dir / "normas.csv", inlinks,
    )
    n_nodes, n_edges = export_grafo_json(vault, export_dir / "grafo.json",
                                         inlinks)
    counts["grafo_nodes"] = n_nodes
    counts["grafo_edges"] = n_edges
    return counts
