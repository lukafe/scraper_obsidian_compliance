"""Scale the enrichment + LLM gap analysis across all jurisdictions.

Uses ThreadPoolExecutor for parallelism. Gemini's SDK is thread-safe and the
bottleneck is API latency (~10–20s per call). 6 workers = ~6x speedup.

Run:
    GEMINI_API_KEY=... .venv/bin/python -m src.run_pilot_scale [country1 country2 ...]

If no countries specified, runs all that have notes and don't yet have an
overview at `vault/_business/jur/{CC}.md`.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from . import business_schema as bs
from . import enrichment, gap_analyzer, overviews, typed_relations, export
from .gemini_client import GeminiClient, GeminiConfig
from .vault import Note, Vault

log = logging.getLogger(__name__)


def analyze_one_note(client: GeminiClient, note: Note,
                     analysis_model: str) -> tuple[str, Optional[dict], float]:
    """Worker: runs gap analyzer on one note. Returns (id, findings, cost)."""
    cost_before = client.ledger.total_cost()
    findings = gap_analyzer.analyze_norm_body(
        client, model=analysis_model,
        note_id=note.id, country=note.country,
        jurisdiction=note.jurisdiction, note_type=note.type,
        regulator=note.regulator, date_str=note.date,
        title=note.title, body=note.body,
        thinking_budget=4000, max_output_tokens=4000,
    )
    cost = client.ledger.total_cost() - cost_before
    return note.id, findings, cost


def run_country(
    vault: Vault, client: GeminiClient, country: str,
    *, analysis_model: str = "gemini-2.5-pro",
    max_workers: int = 6, skip_if_enriched: bool = True,
) -> dict:
    """Full pipeline for one country.

    1. Baseline enrichment (frontmatter fields with nulls)
    2. LLM gap analysis on every note with body (parallel)
    3. Typed relations + Fit CertiK section
    4. Overview note
    """
    country = country.upper()
    t0 = time.time()

    # 1) Baseline enrichment
    scanned, modified = enrichment.enrich_country(vault, country)

    # 2) Gather notes that need LLM analysis
    notes = [
        n for n in vault.iter_notes()
        if n.country == country and n.status != "quarantine"
        and n.body and len(n.body.strip()) > 200
    ]
    if skip_if_enriched:
        # Skip notes that already carry verbatim evidence on every
        # extracted Phase-1 field AND have an `escopo`. Anything else is
        # a Phase-1 upgrade target — re-analyze so the new prompt can
        # produce evidence quotes and the validators (Phase 3) can
        # demote unsupported calls.
        def _fully_grounded(extra: dict) -> bool:
            if not extra.get("escopo"):
                return False
            for f in bs.EVIDENCE_FIELDS:
                if extra.get(f) is not None and not extra.get(f"{f}_evidence"):
                    return False
            return True

        notes = [n for n in notes if not _fully_grounded(n.extra)]

    log.info("country=%s scanned=%d enriched=%d need_llm=%d (workers=%d)",
             country, scanned, modified, len(notes), max_workers)

    cost_start = client.ledger.total_cost()
    analyzed = 0
    if notes:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(analyze_one_note, client, n, analysis_model): n
                for n in notes
            }
            done = 0
            for fut in as_completed(futures):
                done += 1
                note = futures[fut]
                try:
                    note_id, findings, _cost = fut.result()
                except Exception as e:
                    log.warning("worker failed %s: %s", note.id, e)
                    continue
                if findings:
                    enrichment.apply_llm_findings(note, findings)
                    vault.write(note)
                    analyzed += 1
                if done % 10 == 0:
                    log.info(
                        "  %s progress: %d/%d analyzed=%d cost=$%.2f",
                        country, done, len(notes), analyzed,
                        client.ledger.total_cost() - cost_start,
                    )

    # 3) Re-derive services + typed relations + Fit CertiK on every note
    n_rel = 0
    for note in vault.iter_notes():
        if note.country != country or note.status == "quarantine":
            continue
        services = bs.derive_services_from_triggers(note.extra)
        if services != (note.extra.get("servicos_certik_aplicaveis") or []):
            note.extra["servicos_certik_aplicaveis"] = services
        if typed_relations.write_note_extensions(note, vault):
            n_rel += 1

    # 4) Overview
    overview_path = overviews.upsert_overview(vault, country)

    cost = client.ledger.total_cost() - cost_start
    elapsed = time.time() - t0
    summary = {
        "country": country, "scanned": scanned, "modified": modified,
        "llm_analyzed": analyzed, "llm_target": len(notes),
        "relations_written": n_rel, "overview": str(overview_path),
        "cost_usd": round(cost, 4), "elapsed_s": round(elapsed, 1),
    }
    log.info("country=%s DONE %s", country, summary)
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("countries", nargs="*",
                        help="ISO codes (e.g. JP CA US). Default: all without overview.")
    parser.add_argument("--max-workers", type=int, default=6,
                        help="Threads per country.")
    parser.add_argument("--analysis-model", default="gemini-2.5-pro")
    parser.add_argument("--force", action="store_true",
                        help="Re-analyze even if escopo is already filled.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s :: %(message)s",
        stream=sys.stderr,
    )

    vault = Vault("./vault")

    if args.countries:
        countries = [c.upper() for c in args.countries]
    else:
        # Discover all countries from existing notes, skip those already with overview.
        seen = set(n.country for n in vault.iter_notes() if n.country)
        seen.discard("INTL"); seen.discard("EU")  # supranational handled separately
        already = {p.stem.upper() for p in (vault.root / "_business" / "jur").glob("*.md")}
        countries = sorted(seen - already)

    log.info("countries to process: %s", countries)
    client = GeminiClient(GeminiConfig(analysis_model=args.analysis_model))

    all_summaries = []
    for c in countries:
        try:
            s = run_country(vault, client, c, analysis_model=args.analysis_model,
                            max_workers=args.max_workers,
                            skip_if_enriched=not args.force)
            all_summaries.append(s)
        except KeyboardInterrupt:
            log.warning("interrupted")
            break
        except Exception as e:
            log.exception("country %s failed: %s", c, e)

    # Final export across everything
    counts = export.export_all(vault)
    log.info("FINAL EXPORT %s", counts)
    log.info("TOTAL COST: $%.4f tokens=%d",
             client.ledger.total_cost(), client.ledger.total_tokens())

    print("\n=== ALL DONE ===")
    for s in all_summaries:
        print(f"  {s['country']}: analyzed={s['llm_analyzed']}/{s['llm_target']} "
              f"rel={s['relations_written']} cost=${s['cost_usd']} time={s['elapsed_s']}s")
    print(f"\n  total cost: ${client.ledger.total_cost():.4f}")
    print(f"  export: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
