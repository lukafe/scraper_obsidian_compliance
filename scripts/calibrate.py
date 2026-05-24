"""Phase 5 — opportunity-score weight calibration / sensitivity analysis.

Without a held-out expert ranking from CertiK BD we cannot do supervised
tuning yet. What we CAN do — and what this script does — is sweep the
40/40/20 weight space and report:

  * Robust top-K: countries that appear in the top-K of EVERY weight
    combination explored (insensitive to the operator's choice).
  * Weight-sensitive countries: top-K appearances only at extreme
    weights, signalling the ranking depends on the operator.
  * Per-country rank range across the sweep (min, median, max).
  * Pearson correlation of each weight combination vs the current
    production formula (0.40 / 0.40 / 0.20), so a future expert
    ranking can be plugged in via --expert path/to/csv.

The sweep is small on purpose — every (urgency, intensity, maturity)
triplet drawn from {0.2, 0.3, 0.4, 0.5} that sums to 1.0. 10 grids,
no LLM cost.

Usage
-----
    python3 scripts/calibrate.py
    python3 scripts/calibrate.py --top-k 12 --expert path/to/bd_ranking.csv

When `--expert` is given, the script picks the weight combination whose
ranking best correlates with the expert column and prints the suggested
weights.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


# These constants MUST match web/lib/scoring.ts. Any change here without
# updating both sides is a calibration bug.
MATURITY_RANK = {"alta": 3, "media": 2, "baixa": 1, "desconhecido": 0}
PAST_DUE_FLOOR = 50.0
PAST_DUE_HALF_LIFE_DAYS = 365.0
NO_DEADLINE_KNOWN_REGIME = 30.0
NO_DEADLINE_UNKNOWN_REGIME = 0.0
FUTURE_HORIZON_DAYS = 730.0


def urgency_component(days, regime) -> float:
    if days is None:
        return NO_DEADLINE_KNOWN_REGIME if regime else NO_DEADLINE_UNKNOWN_REGIME
    days = float(days)
    if days < 0:
        months_past = abs(days) / 30.0
        decay = (months_past * 30.0) / PAST_DUE_HALF_LIFE_DAYS
        return max(PAST_DUE_FLOOR, 100.0 - decay * (100.0 - PAST_DUE_FLOOR))
    return max(0.0, 100.0 - (days / FUTURE_HORIZON_DAYS) * 100.0)


def score(j, *, wu: float, wi: float, wm: float) -> float:
    urgency = urgency_component(j["urgencia_deadline_dias"], j["regime"])
    intensity = (float(j["n_servicos"]) / 14.0) * 100.0
    maturity = ((MATURITY_RANK.get(j.get("maturidade_mercado") or "desconhecido", 0)) / 3.0) * 100.0
    return wu * urgency + wi * intensity + wm * maturity


def _load_jurisdictions(path: Path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append({
                "iso": r["iso"],
                "pais": r["pais"],
                "n_servicos": int(r["n_servicos"] or 0),
                "regime": r.get("regime") or None,
                "maturidade_mercado": r.get("maturidade_mercado") or None,
                "urgencia_deadline_dias": (
                    int(r["urgencia_deadline_dias"])
                    if r.get("urgencia_deadline_dias") else None
                ),
            })
    return rows


def _weight_grid(step: float = 0.1, lo: float = 0.1, hi: float = 0.7):
    """Yield every (wu, wi, wm) triplet whose components are multiples of
    `step` in [lo, hi] and sum to 1.0. Filters out degenerate grids
    (any weight < 0.1 hurts interpretability).
    """
    # work in tenths to avoid float-precision pain
    s = int(round(step * 10))
    lo_i = int(round(lo * 10))
    hi_i = int(round(hi * 10))
    for u in range(lo_i, hi_i + 1, s):
        for i in range(lo_i, hi_i + 1, s):
            m = 10 - u - i
            if lo_i <= m <= hi_i:
                yield (u / 10.0, i / 10.0, m / 10.0)


def _pearson(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    den_a = (sum((x - mean_a) ** 2 for x in a)) ** 0.5
    den_b = (sum((y - mean_b) ** 2 for y in b)) ** 0.5
    if den_a == 0 or den_b == 0:
        return 0.0
    return num / (den_a * den_b)


def _load_expert(path: Path) -> dict[str, float]:
    """Expert CSV: two columns `iso`, `rank` (1 = best). Higher numbers =
    less attractive, smaller rank = more attractive.
    """
    out = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            iso = r["iso"].strip().upper()
            try:
                out[iso] = float(r["rank"])
            except (KeyError, ValueError):
                continue
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--input",
        default=str(REPO_ROOT / "vault" / "_export" / "jurisdicoes.csv"),
    )
    p.add_argument("--top-k", type=int, default=12)
    p.add_argument("--expert", type=str, default=None,
                   help="Optional CSV of expert rankings (cols: iso, rank)")
    args = p.parse_args()

    juris = _load_jurisdictions(Path(args.input))
    print(f"Loaded {len(juris)} jurisdictions.\n")

    weights = list(_weight_grid())
    print(f"Weight grid: {len(weights)} combinations")
    print(f"Top-K window: {args.top_k}\n")

    # rank[iso][weight-index] = rank in that scenario (1 = best)
    iso_rank_history: dict[str, list[int]] = {j["iso"]: [] for j in juris}
    iso_topk_count: dict[str, int] = {j["iso"]: 0 for j in juris}

    # also build production-formula scores for correlation
    prod_scores = {j["iso"]: score(j, wu=0.4, wi=0.4, wm=0.2) for j in juris}

    per_combo_corr: list[tuple[tuple[float, float, float], float, list[str]]] = []
    for w in weights:
        wu, wi, wm = w
        scored = sorted(
            [(j["iso"], score(j, wu=wu, wi=wi, wm=wm)) for j in juris],
            key=lambda x: -x[1],
        )
        for rank, (iso, _) in enumerate(scored, 1):
            iso_rank_history[iso].append(rank)
            if rank <= args.top_k:
                iso_topk_count[iso] += 1

        topk = [iso for iso, _ in scored[:args.top_k]]
        # correlation vs production
        new_scores = dict(scored)
        a = [new_scores[iso] for iso in sorted(prod_scores)]
        b = [prod_scores[iso] for iso in sorted(prod_scores)]
        per_combo_corr.append((w, _pearson(a, b), topk))

    # Robust top-K: countries in EVERY weight combination's top-K
    robust = [iso for iso, n in iso_topk_count.items() if n == len(weights)]
    sometimes = [iso for iso, n in iso_topk_count.items()
                 if 0 < n < len(weights)]
    never = [iso for iso, n in iso_topk_count.items() if n == 0]

    print(f"Robust top-{args.top_k} (appear in EVERY weight combo): {len(robust)}")
    for iso in sorted(robust, key=lambda i: statistics.median(iso_rank_history[i])):
        ranks = iso_rank_history[iso]
        print(f"  {iso}  rank range {min(ranks)}-{max(ranks)}  median {int(statistics.median(ranks))}")

    print(f"\nSometimes top-{args.top_k} (weight-sensitive): {len(sometimes)}")
    for iso in sorted(sometimes,
                      key=lambda i: -iso_topk_count[i]):
        n = iso_topk_count[iso]
        ranks = iso_rank_history[iso]
        share = n / len(weights) * 100
        print(f"  {iso}  in {n}/{len(weights)} ({share:>4.0f}%)  "
              f"rank {min(ranks)}-{max(ranks)} (median {int(statistics.median(ranks))})")

    print(f"\nNever top-{args.top_k}: {len(never)} ({', '.join(sorted(never))})\n")

    if args.expert:
        expert = _load_expert(Path(args.expert))
        if not expert:
            print("Expert file loaded zero rows — check the format.")
            return 1
        # For each weight combination, compare its ordering against the
        # expert ordering on the subset that overlaps.
        best = None
        scored_combos = []
        for w in weights:
            wu, wi, wm = w
            our = sorted(
                [(j["iso"], score(j, wu=wu, wi=wi, wm=wm)) for j in juris
                 if j["iso"] in expert],
                key=lambda x: -x[1],
            )
            our_rank = {iso: r for r, (iso, _) in enumerate(our, 1)}
            isos = sorted(set(our_rank) & set(expert))
            if len(isos) < 3:
                continue
            a = [our_rank[i] for i in isos]
            b = [expert[i] for i in isos]
            corr = _pearson(a, b)
            scored_combos.append((corr, w))
        if scored_combos:
            scored_combos.sort(reverse=True)
            print("Best 5 weight combinations vs expert ranking:")
            for corr, w in scored_combos[:5]:
                print(f"  weights={w}  pearson={corr:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
