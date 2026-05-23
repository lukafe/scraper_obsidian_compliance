"""Orchestrator: drives the SEED -> SCRAPE -> ANALYZE -> REPEAT loop.

Iterates per country until convergence or a budget cap. The "work queue" is
always a frontmatter query against the vault — there is no separate state
store.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from . import moc as moc_mod
from .analyzer import Analysis, AnalyzerEngine, Citation, Related
from .anthropic_client import AnthropicClient, AnthropicConfig
from .discovery import COUNTRY_NAMES, CandidateNorm, DiscoveryEngine
from .normalizer import normalize
from .scraper import FileCache, HttpScraper
from .vault import (
    META_DIR,
    Note,
    SUPRANATIONAL_COUNTRY,
    Vault,
    make_id,
    wikilink,
)

log = logging.getLogger(__name__)


# ---------- Config -------------------------------------------------------


@dataclass
class Config:
    vault_path: str = "./vault"
    cache_path: str = "./cache"
    countries: list[str] = field(default_factory=list)
    seed_supranational: bool = True
    node_types: list[str] = field(default_factory=lambda: ["statute", "regulation", "guidance", "case_law"])

    confidence_threshold: float = 0.70
    convergence_threshold: float = 0.85

    max_cycles_per_country: int = 4
    max_new_nodes_per_cycle: int = 25
    max_depth: int = 3
    max_seed_per_country: int = 15
    max_tokens_per_country_per_cycle: int = 250_000

    translate: bool = True
    target_language: str = "en"

    user_agent: str = "crypto-lawmap/0.1"
    http_timeout_seconds: float = 30.0
    rate_limit_per_host_seconds: float = 1.5
    respect_robots_txt: bool = True
    playwright_fallback: bool = True

    provider: str = "anthropic"   # "anthropic" or "gemini"
    models: dict[str, str] = field(default_factory=lambda: {
        "discovery": "claude-sonnet-4-6",
        "analysis": "claude-sonnet-4-6",
        "extraction": "claude-haiku-4-5-20251001",
    })
    models_anthropic: dict[str, str] = field(default_factory=dict)
    models_gemini: dict[str, str] = field(default_factory=dict)
    web_search: dict = field(default_factory=lambda: {"enabled": True, "max_uses_per_call": 5})
    retry: dict = field(default_factory=lambda: {"max_attempts": 5, "base_delay_seconds": 2.0, "max_delay_seconds": 60.0})
    log_level: str = "INFO"

    # Force-include: norms the user explicitly wants seeded for each country.
    # Each entry: { title_hint: <str>, url_hint: <str|null>, type: <str|null>,
    #               regulator: <str|null>, date: <str|null> }.
    # url_hint > 0 chars  -> verify + admit directly (skip discovery LLM).
    # url_hint empty       -> targeted semantic resolution via the LLM.
    force_include: dict[str, list[dict]] = field(default_factory=dict)

    # Per-prompt thinking budgets (Gemini 2.5 only — Anthropic ignores).
    # 0 disables (faster, cheaper); higher = deeper reasoning.
    thinking_budgets: dict[str, int] = field(default_factory=lambda: {
        "discovery": 0,
        "analysis": 4000,
        "extraction": 0,
    })

    # Per-prompt max output tokens.
    max_output_tokens: dict[str, int] = field(default_factory=lambda: {
        "discovery": 16000,
        "analysis": 8000,
        "extraction": 8000,
    })

    def active_models(self) -> dict[str, str]:
        """Pick the right per-provider model map, falling back to legacy `models`."""
        if self.provider == "gemini" and self.models_gemini:
            return self.models_gemini
        if self.provider == "anthropic" and self.models_anthropic:
            return self.models_anthropic
        return self.models

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        # Only assign known fields; ignore unknown keys.
        cfg = cls()
        for k, v in raw.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


# ---------- Per-cycle metrics -------------------------------------------


@dataclass
class CycleStats:
    country: str
    cycle: int
    new_nodes_citation: int = 0
    new_nodes_semantic: int = 0
    new_nodes_quarantine: int = 0
    nodes_scraped: int = 0
    nodes_analyzed: int = 0
    refs_total: int = 0
    refs_known: int = 0
    api_tokens: int = 0
    api_cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
    halted_reason: Optional[str] = None

    @property
    def convergence(self) -> float:
        if self.refs_total == 0:
            return 1.0
        return self.refs_known / self.refs_total

    def to_dict(self) -> dict:
        return {
            "country": self.country,
            "cycle": self.cycle,
            "new_citation": self.new_nodes_citation,
            "new_semantic": self.new_nodes_semantic,
            "new_quarantine": self.new_nodes_quarantine,
            "scraped": self.nodes_scraped,
            "analyzed": self.nodes_analyzed,
            "refs_total": self.refs_total,
            "refs_known": self.refs_known,
            "convergence": round(self.convergence, 3),
            "tokens": self.api_tokens,
            "cost_usd": round(self.api_cost_usd, 4),
            "elapsed_s": round(self.elapsed_seconds, 1),
            "halted_reason": self.halted_reason,
        }


# ---------- Orchestrator -------------------------------------------------


class Orchestrator:
    def __init__(
        self,
        cfg: Config,
        *,
        dry_run: bool = False,
        skip_scrape: bool = False,
        skip_analyze: bool = False,
    ):
        self.cfg = cfg
        self.dry_run = dry_run
        self.skip_scrape = skip_scrape
        self.skip_analyze = skip_analyze

        self.vault = Vault(cfg.vault_path)
        self.cache = FileCache(cfg.cache_path)
        self.scraper = HttpScraper(
            cache=self.cache,
            user_agent=cfg.user_agent,
            timeout=cfg.http_timeout_seconds,
            rate_limit_seconds=cfg.rate_limit_per_host_seconds,
            respect_robots=cfg.respect_robots_txt,
            playwright_fallback=cfg.playwright_fallback,
        )

        models = cfg.active_models()
        provider = (cfg.provider or "anthropic").lower()
        if provider == "gemini":
            from .gemini_client import GeminiClient, GeminiConfig
            gem_cfg = GeminiConfig(
                discovery_model=models.get("discovery", "gemini-2.5-flash"),
                analysis_model=models.get("analysis", "gemini-2.5-flash"),
                extraction_model=models.get("extraction", "gemini-2.5-flash-lite"),
                web_search_enabled=bool(cfg.web_search.get("enabled", True)),
                max_attempts=int(cfg.retry.get("max_attempts", 5)),
                base_delay_seconds=float(cfg.retry.get("base_delay_seconds", 2.0)),
                max_delay_seconds=float(cfg.retry.get("max_delay_seconds", 60.0)),
            )
            self.client = GeminiClient(gem_cfg)
            discovery_model = gem_cfg.discovery_model
            analysis_model = gem_cfg.analysis_model
            log.info("provider=gemini discovery=%s analysis=%s extraction=%s",
                     gem_cfg.discovery_model, gem_cfg.analysis_model, gem_cfg.extraction_model)
        else:
            ant_cfg = AnthropicConfig(
                discovery_model=models.get("discovery", "claude-sonnet-4-6"),
                analysis_model=models.get("analysis", "claude-sonnet-4-6"),
                extraction_model=models.get("extraction", "claude-haiku-4-5-20251001"),
                web_search_enabled=bool(cfg.web_search.get("enabled", True)),
                web_search_max_uses=int(cfg.web_search.get("max_uses_per_call", 5)),
                max_attempts=int(cfg.retry.get("max_attempts", 5)),
                base_delay_seconds=float(cfg.retry.get("base_delay_seconds", 2.0)),
                max_delay_seconds=float(cfg.retry.get("max_delay_seconds", 60.0)),
            )
            self.client = AnthropicClient(ant_cfg)
            discovery_model = ant_cfg.discovery_model
            analysis_model = ant_cfg.analysis_model
            log.info("provider=anthropic discovery=%s analysis=%s extraction=%s",
                     ant_cfg.discovery_model, ant_cfg.analysis_model, ant_cfg.extraction_model)

        # Make active models accessible elsewhere (used by normalize for extraction).
        self.active_models_map = models

        self.discovery = DiscoveryEngine(
            self.client,
            self.scraper,
            discovery_model=discovery_model,
            max_seed_per_country=cfg.max_seed_per_country,
            max_output_tokens=int(cfg.max_output_tokens.get("discovery", 16000)),
            thinking_budget=int(cfg.thinking_budgets.get("discovery", 0)),
        )
        self.analyzer = AnalyzerEngine(
            self.client,
            model=analysis_model,
            max_output_tokens=int(cfg.max_output_tokens.get("analysis", 8000)),
            thinking_budget=int(cfg.thinking_budgets.get("analysis", 4000)),
        )

        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.all_stats: list[CycleStats] = []

    # ===================================================================
    # Top-level entry points
    # ===================================================================

    def run(self, countries: list[str], *, seed_only: bool = False) -> None:
        log.info("run start id=%s countries=%s seed_only=%s",
                 self.run_id, countries, seed_only)
        for country in countries:
            try:
                self._run_country(country, seed_only=seed_only)
            except KeyboardInterrupt:
                log.warning("interrupted by user during country=%s", country)
                break
            except Exception as e:
                log.exception("country failed country=%s err=%s", country, e)
                continue

        # Always regenerate MOCs at the end.
        for c in countries:
            try:
                moc_mod.write_country_moc(self.vault, c)
            except Exception as e:
                log.warning("MOC write failed country=%s err=%s", c, e)
        try:
            moc_mod.write_global_moc(self.vault, countries)
        except Exception as e:
            log.warning("Global MOC write failed err=%s", e)
        try:
            from . import moc_axis
            moc_axis.write_axis_mocs(self.vault)
        except Exception as e:
            log.warning("Axis MOC write failed err=%s", e)

        self._write_run_log()
        self.scraper.close()
        log.info("run end id=%s cost=$%.4f tokens=%d",
                 self.run_id, self.client.ledger.total_cost(),
                 self.client.ledger.total_tokens())

    # ===================================================================
    # Per-country driver
    # ===================================================================

    def _run_country(self, country: str, *, seed_only: bool) -> None:
        country = country.upper()
        log.info("=== country=%s ===", country)

        # Force-include runs every time (idempotent — vault.upsert dedups by id).
        # Lets the user add new must-haves to config and re-run to backfill.
        self._force_include_for(country)

        # Auto-discovery seed only on the very first cycle for this country.
        if not self._has_seed_nodes(country):
            self._seed(country)

        if seed_only:
            return

        for cycle in range(1, self.cfg.max_cycles_per_country + 1):
            t0 = time.time()
            tokens_before = self.client.ledger.total_tokens()
            cost_before = self.client.ledger.total_cost()
            stats = CycleStats(country=country, cycle=cycle)

            # 1. SCRAPE every `verified` for this country.
            if not self.skip_scrape:
                stats.nodes_scraped = self._scrape_pending(country)

            # 2. ANALYZE every `scraped` for this country.
            new_nodes_this_cycle = 0
            if not self.skip_analyze:
                new_nodes_this_cycle = self._analyze_pending(country, cycle, stats)

            stats.api_tokens = self.client.ledger.total_tokens() - tokens_before
            stats.api_cost_usd = self.client.ledger.total_cost() - cost_before
            stats.elapsed_seconds = time.time() - t0

            # 3. Halt checks.
            halted = self._halt_reason(stats, cycle)
            if halted:
                stats.halted_reason = halted
            self.all_stats.append(stats)
            log.info("cycle done country=%s cycle=%d %s",
                     country, cycle, json.dumps(stats.to_dict()))
            if halted:
                log.info("country halted country=%s reason=%s", country, halted)
                break

            # Nothing left in the queue? Done.
            if not self._has_pending_work(country):
                stats.halted_reason = "queue_empty"
                log.info("country halted country=%s reason=queue_empty", country)
                break

    # -----------------------------------------------------------------
    # Phases
    # -----------------------------------------------------------------

    def _seed(self, country: str) -> None:
        if self.dry_run:
            log.info("dry-run: would seed country=%s", country)
            return
        cands = self.discovery.seed_country(country)
        for cand in cands:
            self._admit_candidate(
                cand,
                cycle=0,
                discovered_via="seed",
                depth=0,
            )
        # Optionally seed supranational bodies on the first country only.
        if self.cfg.seed_supranational and country == (self.cfg.countries or [country])[0]:
            log.info("seeding supranational bodies (INTL)")
            intl_cands = self.discovery.seed_country(SUPRANATIONAL_COUNTRY)
            for cand in intl_cands:
                self._admit_candidate(cand, cycle=0, discovered_via="seed", depth=0)

    def _force_include_for(self, country: str) -> None:
        """Admit user-specified must-have norms before auto-discovery runs.

        Two paths per entry:
          - If `url_hint` is provided -> verify + admit directly (no LLM cost).
          - Otherwise -> targeted semantic resolution to find a primary URL.
        """
        entries = self.cfg.force_include.get(country.upper()) or []
        if not entries:
            return
        log.info("force_include country=%s n=%d", country, len(entries))
        if self.dry_run:
            return

        for entry in entries:
            title_hint = (entry.get("title_hint") or entry.get("title") or "").strip()
            if not title_hint:
                continue
            type_ = (entry.get("type") or "regulation").strip()
            regulator = (entry.get("regulator") or None)
            date_str = entry.get("date")
            url_hint = (entry.get("url_hint") or entry.get("url") or "").strip()
            jurisdiction = COUNTRY_NAMES.get(country.upper(), country)

            if url_hint:
                # Direct admission path: build candidate, verify, admit.
                cand = CandidateNorm(
                    country=country.upper(),
                    jurisdiction=jurisdiction,
                    title=title_hint,
                    title_original=entry.get("title_original"),
                    short_label=entry.get("short_label"),
                    type=type_,
                    regulator=regulator,
                    candidate_url=url_hint,
                    date=date_str,
                )
                self._admit_candidate(cand, cycle=0, discovered_via="seed", depth=0)
            else:
                # Semantic-resolution path: ask the model to find a primary URL.
                resolved = self.discovery.resolve_semantic_suggestion(
                    country=country.upper(),
                    jurisdiction=jurisdiction,
                    title=title_hint,
                    type_=type_,
                    regulator=regulator,
                )
                if resolved is None:
                    log.warning("force_include unresolved title=%r", title_hint)
                    continue
                # Honor the user's type/regulator hints over the model's guess.
                resolved.type = type_
                if regulator and not resolved.regulator:
                    resolved.regulator = regulator
                self._admit_candidate(resolved, cycle=0, discovered_via="seed", depth=0)

    def _scrape_pending(self, country: str) -> int:
        pending = self.vault.query(status="verified", country=country)
        log.info("scrape pending country=%s n=%d", country, len(pending))
        n = 0
        for note in pending:
            if not note.source_url:
                continue
            if self.dry_run:
                continue
            fr = self.scraper.fetch(note.source_url)
            if fr is None or not fr.text.strip():
                log.info("scrape empty url=%s -> quarantine", note.source_url)
                note.status = "quarantine"
                self.vault.write(note)
                continue
            normalized = normalize(
                fr.text,
                translate_to=self.cfg.target_language if self.cfg.translate else None,
                client=self.client,
                translation_model=self.active_models_map.get("extraction"),
            )
            note.body = normalized.body
            if normalized.language and not note.language:
                note.language = normalized.language
            note.status = "scraped"
            self.vault.write(note)
            n += 1
        return n

    def _analyze_pending(self, country: str, cycle: int, stats: CycleStats) -> int:
        pending = self.vault.query(status="scraped", country=country)
        log.info("analyze pending country=%s n=%d", country, len(pending))
        new_nodes = 0

        for note in pending:
            if self.dry_run:
                continue
            depth = int(note.extra.get("depth", 0) or 0)
            analysis = self.analyzer.analyze(
                note_id=note.id,
                country=note.country,
                country_name=COUNTRY_NAMES.get(note.country, note.country),
                jurisdiction=note.jurisdiction,
                regulator=note.regulator,
                title=note.title,
                note_type=note.type,
                body=note.body,
            )

            stats.nodes_analyzed += 1

            # --- citations: deterministic engine ---
            for cit in analysis.citations:
                stats.refs_total += 1
                ref_id = _id_from_citation(cit)
                if self.vault.exists(ref_id):
                    stats.refs_known += 1
                    _attach_reference(note, ref_id, "citation")
                    continue
                # case_law is admitted ONLY if it cites a norm already in the
                # graph — handled implicitly: a case_law citation always has a
                # citing parent (`note`) already in the graph, which is the
                # condition we want. So citations of case_law go through.
                if depth + 1 > self.cfg.max_depth:
                    log.info("depth cap skip ref=%s parent=%s depth=%d",
                             ref_id, note.id, depth + 1)
                    continue
                created = self._admit_citation_node(
                    cit, cycle=cycle, depth=depth + 1, parent_id=note.id
                )
                if created:
                    new_nodes += 1
                    stats.new_nodes_citation += 1
                    _attach_reference(note, ref_id, "citation")
                if new_nodes >= self.cfg.max_new_nodes_per_cycle:
                    break

            # --- related: semantic engine (probabilistic) ---
            if new_nodes < self.cfg.max_new_nodes_per_cycle:
                for rel in analysis.related:
                    if new_nodes >= self.cfg.max_new_nodes_per_cycle:
                        break
                    # case_law admission rule: only if it cites a norm in the graph.
                    if rel.type == "case_law" and depth >= self.cfg.max_depth:
                        continue
                    cand = self.discovery.resolve_semantic_suggestion(
                        country=rel.country,
                        jurisdiction=rel.jurisdiction,
                        title=rel.title,
                        type_=rel.type,
                        regulator=rel.regulator,
                    )
                    if cand is None:
                        continue
                    decision_id, decision = self._admit_candidate(
                        cand,
                        cycle=cycle,
                        discovered_via="semantic",
                        depth=depth + 1,
                        return_decision=True,
                    )
                    if decision_id is None:
                        continue
                    # Track refs whether we promoted or quarantined.
                    stats.refs_total += 1
                    if decision == "existed":
                        stats.refs_known += 1
                    elif decision == "verified":
                        new_nodes += 1
                        stats.new_nodes_semantic += 1
                    elif decision == "quarantine":
                        stats.new_nodes_quarantine += 1
                    # Only link from parent if it's a real (non-quarantine) node.
                    if decision in {"existed", "verified"}:
                        _attach_reference(note, decision_id, "semantic")

            # Mark this note analyzed regardless of how many refs we made.
            note.status = "analyzed"
            self.vault.write(note)

            # Token-budget guard — bail out of this country's cycle early.
            if (
                self.cfg.max_tokens_per_country_per_cycle > 0
                and stats.api_tokens >= self.cfg.max_tokens_per_country_per_cycle
            ):
                log.info("token cap hit country=%s cycle=%d tokens=%d",
                         country, cycle, stats.api_tokens)
                break

        return new_nodes

    # -----------------------------------------------------------------
    # Candidate / citation admission
    # -----------------------------------------------------------------

    def _admit_candidate(
        self,
        cand: CandidateNorm,
        *,
        cycle: int,
        discovered_via: str,
        depth: int = 0,
        return_decision: bool = False,
    ):
        """Verify the candidate and write a (possibly quarantined) node.

        Returns either:
          None                       if `return_decision` is False
          (note_id_or_None, decision) if True, where decision is one of
          'existed' | 'verified' | 'quarantine' | 'drop'
        """
        cand, decision = self.discovery.verify_candidate(
            cand, confidence_threshold=self.cfg.confidence_threshold
        )
        if decision == "drop":
            return (None, "drop") if return_decision else None

        nid = make_id(
            country=cand.country, title=cand.title,
            regulator=cand.regulator, date_str=cand.date,
            short_label=cand.short_label,
        )

        existing = self.vault.read(nid)
        if existing is not None:
            # Dedup — same logical norm already in the vault.
            return (nid, "existed") if return_decision else None

        status = "verified" if decision == "verified" else "quarantine"
        note = Note(
            id=nid,
            country=cand.country,
            jurisdiction=cand.jurisdiction,
            type=cand.type,
            title=cand.title,
            title_original=cand.title_original,
            status=status,
            regulator=cand.regulator,
            source_url=cand.candidate_url,
            source_authority=cand.source_authority,
            confidence=cand.confidence,
            language=cand.language,
            date=cand.date,
            discovered_via=discovered_via,
            cycle=cycle,
            extra={"depth": depth},
        )
        self.vault.upsert(note)
        log.info("admit %s id=%s status=%s conf=%.2f authority=%s",
                 discovered_via, nid, status, cand.confidence or 0.0,
                 cand.source_authority or "?")
        return (nid, decision) if return_decision else None

    def _admit_citation_node(
        self,
        cit: Citation,
        *,
        cycle: int,
        depth: int,
        parent_id: str,
    ) -> bool:
        """Create a `discovered` node from a citation. Returns True if created.

        We DON'T resolve a URL here yet — the next cycle's SEED-like step
        would, but to keep the design simple we treat citation nodes as
        verified-from-text and let the next ANALYZE cycle handle them.

        If the citation includes a candidate_url, we verify it now; otherwise
        we resolve via the semantic-suggestion mechanism (which queries the
        web for a primary source).
        """
        # Build a CandidateNorm and reuse the standard pipeline.
        cand = CandidateNorm(
            country=cit.country,
            jurisdiction=cit.jurisdiction,
            title=cit.title,
            type=cit.type,
            regulator=cit.regulator,
            candidate_url=cit.candidate_url,
            date=cit.date,
        )
        # If no URL provided, try to resolve one via web search.
        if not cand.candidate_url:
            resolved = self.discovery.resolve_semantic_suggestion(
                country=cit.country,
                jurisdiction=cit.jurisdiction,
                title=cit.title,
                type_=cit.type,
                regulator=cit.regulator,
            )
            if resolved is not None:
                cand = resolved
            else:
                # Create a stub with no URL — keeps the citation in the graph
                # but quarantined until a URL can be found.
                nid = make_id(country=cit.country, title=cit.title,
                              regulator=cit.regulator, date_str=cit.date,
                              short_label=cit.short_label)
                if self.vault.exists(nid):
                    return False
                stub = Note(
                    id=nid,
                    country=cit.country,
                    jurisdiction=cit.jurisdiction,
                    type=cit.type,
                    title=cit.title,
                    title_original=cit.title_original,
                    status="quarantine",
                    regulator=cit.regulator,
                    confidence=0.0,
                    discovered_via="citation",
                    cycle=cycle,
                    extra={"depth": depth, "stub_from_parent": parent_id},
                )
                self.vault.upsert(stub)
                return True

        result = self._admit_candidate(
            cand, cycle=cycle, discovered_via="citation",
            depth=depth, return_decision=True,
        )
        nid, decision = result if result else (None, "drop")
        return decision in {"verified", "quarantine"}

    # -----------------------------------------------------------------
    # Loop control
    # -----------------------------------------------------------------

    def _has_seed_nodes(self, country: str) -> bool:
        return any(
            n.discovered_via == "seed"
            for n in self.vault.query(country=country)
        )

    def _has_pending_work(self, country: str) -> bool:
        # SCRAPE queue OR ANALYZE queue is non-empty.
        if self.vault.query(status="verified", country=country):
            return True
        if self.vault.query(status="scraped", country=country):
            return True
        return False

    def _halt_reason(self, stats: CycleStats, cycle: int) -> Optional[str]:
        if cycle >= self.cfg.max_cycles_per_country:
            return "max_cycles"
        new_total = stats.new_nodes_citation + stats.new_nodes_semantic
        if new_total >= self.cfg.max_new_nodes_per_cycle:
            return "max_new_nodes"
        # Convergence: of refs seen this cycle, how many were already nodes?
        if stats.refs_total >= 10 and stats.convergence >= self.cfg.convergence_threshold:
            return f"converged({stats.convergence:.2f})"
        return None

    # -----------------------------------------------------------------
    # Run log
    # -----------------------------------------------------------------

    def _write_run_log(self) -> None:
        log_path = self.vault.root / META_DIR / "run-log.md"
        # Append a section for this run.
        lines: list[str] = []
        if log_path.exists():
            lines.append("")
            lines.append("---")
            lines.append("")
        lines.append(f"## Run {self.run_id}")
        lines.append("")
        lines.append(
            f"- countries: {sorted({s.country for s in self.all_stats})}"
        )
        lines.append(f"- total cycles: {len(self.all_stats)}")
        lines.append(
            f"- total tokens: {self.client.ledger.total_tokens()}, "
            f"cost: ${self.client.ledger.total_cost():.4f}"
        )
        lines.append("")
        lines.append("| country | cycle | new_cit | new_sem | new_qrn | scraped | analyzed | refs | known | conv | tokens | cost | halt |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for s in self.all_stats:
            d = s.to_dict()
            lines.append(
                f"| {d['country']} | {d['cycle']} | {d['new_citation']} | {d['new_semantic']} | "
                f"{d['new_quarantine']} | {d['scraped']} | {d['analyzed']} | "
                f"{d['refs_total']} | {d['refs_known']} | {d['convergence']:.2f} | "
                f"{d['tokens']} | ${d['cost_usd']:.4f} | {d['halted_reason'] or ''} |"
            )

        # Append-or-create.
        mode = "a" if log_path.exists() else "w"
        with open(log_path, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write("# Crypto LawMap — Run log\n\n")
            f.write("\n".join(lines) + "\n")

        # Also dump a structured budget tracker.
        budget_path = self.vault.root / META_DIR / "budget-tracker.json"
        budget = {
            "last_run_id": self.run_id,
            "ledger": self.client.ledger.summary(),
            "cycles": [s.to_dict() for s in self.all_stats],
        }
        budget_path.write_text(json.dumps(budget, indent=2), encoding="utf-8")


# ---------- Helpers -------------------------------------------------------


def _id_from_citation(cit: Citation) -> str:
    return make_id(
        country=cit.country,
        title=cit.title,
        regulator=cit.regulator,
        date_str=cit.date,
        short_label=cit.short_label,
    )


def _attach_reference(note: Note, ref_id: str, ref_type: str) -> None:
    link = wikilink(ref_id)
    if link not in note.references:
        note.references.append(link)
    note.ref_types.setdefault(ref_id, ref_type)


# ---------- CLI -----------------------------------------------------------


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(name)s :: %(message)s",
        stream=sys.stderr,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Crypto LawMap orchestrator")
    parser.add_argument("--config", default="./config.yaml")
    parser.add_argument("--countries", default=None,
                        help="CSV override of config.countries (e.g. BR,US,SG)")
    parser.add_argument("--seed-only", action="store_true")
    parser.add_argument("--no-scrape", action="store_true")
    parser.add_argument("--no-analyze", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cfg = Config.load(args.config)
    _setup_logging(cfg.log_level)

    if args.max_cycles is not None:
        cfg.max_cycles_per_country = args.max_cycles

    if args.countries:
        countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    else:
        countries = [c.strip().upper() for c in cfg.countries or []]
    if not countries:
        log.error("no countries to process (config.countries empty and --countries not given)")
        return 2

    provider = (cfg.provider or "anthropic").lower()
    if not args.dry_run:
        if provider == "gemini":
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
                log.error("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set — refusing to run without it. Use --dry-run to debug structure.")
                return 2
        else:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                log.error("ANTHROPIC_API_KEY is not set — refusing to run without it. Use --dry-run to debug structure.")
                return 2

    orch = Orchestrator(
        cfg,
        dry_run=args.dry_run,
        skip_scrape=args.no_scrape,
        skip_analyze=args.no_analyze,
    )
    orch.run(countries, seed_only=args.seed_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
