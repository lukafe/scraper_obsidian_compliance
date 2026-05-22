# Crypto LawMap

Self-expanding knowledge graph of global crypto legislation, materialized as an
Obsidian vault. Each norm is a `.md` note; state lives in YAML frontmatter; the
graph is the wikilinks between notes. No external database — the vault is the
source of truth.

## How it works

A loop runs a five-state machine per note:

```
discovered -> verified -> scraped -> analyzed
                 \-> quarantine (low confidence)
```

1. **SEED** — for each country in `config.yaml`, ask Claude (with native web
   search) for primary norms (statutes, regulations, guidance, case law).
2. **SCRAPE** — fetch each verified URL (HTML / PDF / JS fallback) and write
   normalized markdown into the note body.
3. **ANALYZE** — Claude reads the body and emits two lists:
   - **citations**: explicit references to other norms (deterministic, safe).
   - **related**: semantically related but uncited (probabilistic, isolated to
     `/_quarantine` until confidence clears the threshold).
4. **REPEAT** — until budget caps trip or convergence is reached.
5. **MOC** — regenerate `/_MOC/{country}.md` and append to `/_meta/run-log.md`.

## Quick start

```bash
cd crypto-lawmap
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium     # only if you need JS fallback

export ANTHROPIC_API_KEY=sk-ant-...

# Smoke test the seed step for a single country, no full loop:
python -m src.orchestrator --seed-only --countries BR

# Run the full loop on all countries in config.yaml:
python -m src.orchestrator
```

## CLI

```
python -m src.orchestrator [options]

  --config PATH              Path to config.yaml (default: ./config.yaml)
  --countries CSV            Override config.countries (e.g. BR,US,SG)
  --seed-only                Only run SEED + verification, then exit
  --no-scrape                Skip SCRAPE phase (debug)
  --no-analyze               Skip ANALYZE phase (debug)
  --max-cycles N             Override config.max_cycles_per_country
  --dry-run                  Don't write to vault or call APIs (planning only)
```

## Vault layout

```
vault/
  BR/    BR-IN701-2024.md, BR-LEI14478-2022.md, ...
  US/    SG/    AE/    ...
  INTL/  INTL-FATF-R16.md, ...
  _quarantine/   low-confidence nodes (not part of the graph)
  _MOC/          Map of Content per country (auto-generated)
  _meta/         run-log.md, budget-tracker.json
```

## Note schema

Every `.md` note carries this frontmatter:

```yaml
---
id: BR-IN701-2024
country: BR
jurisdiction: Brasil
type: regulation              # statute | regulation | guidance | case_law
regulator: BCB
title: Instrução Normativa BCB nº 701
status: analyzed              # discovered | verified | scraped | analyzed | quarantine
source_url: https://www.bcb.gov.br/...
source_authority: primary     # primary | secondary | tertiary
confidence: 0.95
language: pt
date: 2024-11-15
discovered_via: seed          # seed | citation | semantic
cycle: 1
references: ["[[BR-LEI14478-2022]]", "[[INTL-FATF-R16]]"]
ref_types: { "BR-LEI14478-2022": citation, "INTL-FATF-R16": semantic }
---
```

## Self-policing

Every new node carries a `confidence` score combining (a) source authority
(`primary` / `secondary` / `tertiary`), (b) URL liveness (HTTP 200), and
(c) title↔content match. Below `confidence_threshold` (default 0.70) the node
moves to `/_quarantine` and stays out of the graph. The loop never blocks on
human review — quarantine *is* the safety mechanism.

## Convergence

A country halts when:
- the fraction of new references that map to existing nodes in a cycle exceeds
  `convergence_threshold` (default 0.85), or
- any budget cap (`max_cycles_per_country`, `max_new_nodes_per_cycle`,
  `max_depth`, `max_tokens_per_country_per_cycle`) is hit.

`case_law` nodes are only admitted when they cite a norm already in the graph
— this keeps jurisprudence anchored and prevents unbounded growth.
