"""Phase 2 CLI — gold-set sampling, seeding and F1 reporting.

Workflow
--------

    # 1. Pick a stratified 100-norm sample and write one YAML seed per
    #    norm under vault/_export/ground_truth/, pre-filled with the
    #    current LLM extraction. The human's job is to review-and-edit
    #    each file, not to annotate from scratch.
    python3 scripts/gold.py seed --n 100

    # 2. The labeller opens each .yaml, checks each value against the
    #    source URL, pastes evidence quotes if missing, and flips
    #    `reviewed: true` once done.

    # 3. Report per-field F1 of the LLM extraction against the
    #    reviewed gold rows. Optionally save the current numbers as
    #    the baseline for CI drift detection.
    python3 scripts/gold.py report
    python3 scripts/gold.py report --save-baseline

Gold YAML schema (every seed starts as a draft with reviewed: false):

    id: BR-RESOLUTIONBCB14-2017
    note_id: BR-RESOLUTIONBCB14-2017
    country: BR
    source_url: https://...
    reviewed: false          # FLIP TO TRUE AFTER HAND-REVIEW
    reviewer: ""             # your name / handle
    reviewed_at: ""          # YYYY-MM-DD

    # === The 13 structured signals ============================
    regime: licenciamento
    regime_evidence: >-
      verbatim quote from the source text supporting this call
    status_regulatorio: vigente
    status_regulatorio_evidence: >-
      ...
    ...
    notes: |
      free-form labeller notes (edge cases, things to revisit)
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src import business_schema as bs  # noqa: E402
from src import gold_set as gs  # noqa: E402

# Vault is only needed when seeding or reporting from the live vault.
# CI uses --from-json to read the committed dashboard JSON instead.
try:
    from src.vault import Vault  # noqa: E402
except Exception:  # missing python-frontmatter / etc — CI mode
    Vault = None  # type: ignore[assignment]

DEFAULT_GOLD_DIR = REPO_ROOT / "vault" / "_export" / "ground_truth"


def _collect_candidates(vault: Vault) -> list[tuple[str, str, dict]]:
    """Pick every non-quarantine, analyzed norm with extracted signals
    (at least one of regime / status / a boolean trigger is non-null)."""
    out = []
    for n in vault.iter_notes():
        if n.status != "analyzed":
            continue
        extra = n.extra
        has_signal = (
            extra.get("regime")
            or extra.get("status_regulatorio")
            or any(extra.get(k) is not None for k in bs.SERVICE_TRIGGERS)
        )
        if not has_signal:
            continue
        out.append((n.id, n.country, dict(extra)))
    return out


def _seed_payload(note_id: str, country: str, extra: dict, source_url: str | None) -> dict:
    """Build the YAML payload for one gold seed."""
    payload: dict = {
        "id": note_id,
        "note_id": note_id,
        "country": country,
        "source_url": source_url,
        "reviewed": False,
        "reviewer": "",
        "reviewed_at": "",
    }
    for f in gs.GOLD_FIELDS:
        payload[f] = extra.get(f)
        if f.startswith("exige_") or f in (
            "regime", "status_regulatorio", "deadline_principal", "tipo_deadline",
        ):
            payload[f"{f}_evidence"] = extra.get(f"{f}_evidence")
    payload["notes"] = ""
    return payload


def cmd_seed(args: argparse.Namespace) -> int:
    vault = Vault(args.vault)
    candidates = _collect_candidates(vault)
    print(f"Pool of analyzable norms: {len(candidates)}")
    if not candidates:
        return 0
    picked = gs.stratified_sample(candidates, n=args.n)
    print(f"Stratified sample: {len(picked)} norms")
    # Brief stratum breakdown
    strata = Counter()
    for nid, country, extra in picked:
        strata[gs._stratum_key(extra, country)] += 1
    print("\nTop strata (region, regime, intensity):")
    for key, n in strata.most_common(10):
        print(f"  {key}: {n}")

    gold_dir = Path(args.gold_dir)
    written = 0
    skipped = 0
    for nid, country, extra in picked:
        out_path = gold_dir / f"{nid}.yaml"
        if out_path.exists() and not args.overwrite:
            skipped += 1
            continue
        note = vault.read(nid)
        source_url = note.source_url if note else None
        payload = _seed_payload(nid, country, extra, source_url)
        gs.dump_seed(out_path, payload)
        written += 1
    print(f"\nSeeds written: {written}  skipped (existing): {skipped}")
    print(f"Open `{gold_dir}/<note_id>.yaml`, review each value, set `reviewed: true`.")
    return 0


def _load_predictions_from_vault(vault, note_ids: set[str]) -> dict[str, dict]:
    """Current LLM extraction for the given note ids (read straight from
    the vault — bypasses CSV round-trip noise)."""
    out: dict[str, dict] = {}
    for n in vault.iter_notes():
        if n.id not in note_ids:
            continue
        extra = dict(n.extra)
        out[n.id] = {f: extra.get(f) for f in gs.GOLD_FIELDS}
    return out


def _load_predictions_from_json(path: Path, note_ids: set[str]) -> dict[str, dict]:
    """Read predictions from the committed dashboard JSON (web/public/data/
    normas.json). Same shape as the vault-extracted rows for the comparator.
    Used by CI where the vault is not checked in.
    """
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for row in data:
        if row.get("id") not in note_ids:
            continue
        out[row["id"]] = {f: row.get(f) for f in gs.GOLD_FIELDS}
    return out


def cmd_report(args: argparse.Namespace) -> int:
    gold_dir = Path(args.gold_dir)
    gold = gs.load_gold_dir(gold_dir)
    if not gold:
        print(f"No reviewed gold rows under {gold_dir} — nothing to score.")
        return 0

    if args.from_json:
        pred = _load_predictions_from_json(Path(args.from_json), set(gold))
    else:
        if Vault is None:
            print("Vault module unavailable; pass --from-json <normas.json>.")
            return 2
        vault = Vault(args.vault)
        pred = _load_predictions_from_vault(vault, set(gold))

    metrics = gs.compare(gold, pred)
    print(f"Reviewed gold rows: {len(gold)}  Predictions matched: {len(pred)}\n")
    print(f"{'field':38s} {'tp':>4s} {'fp':>4s} {'fn':>4s} "
          f"{'P':>6s} {'R':>6s} {'F1':>6s}  {'support':>7s}")
    print("-" * 84)
    for f in gs.GOLD_FIELDS:
        m = metrics[f]
        print(
            f"{f:38s} {m.tp:>4d} {m.fp:>4d} {m.fn:>4d} "
            f"{m.precision:>6.2f} {m.recall:>6.2f} {m.f1:>6.2f}  {m.support:>7d}"
        )
    print("-" * 84)
    print(f"{'overall (support-weighted F1)':38s} {' ':>14s} "
          f"{' ':>13s} {gs.overall_f1(metrics):>6.2f}")

    # Highlight up to 5 disagreements per field for the reviewer.
    print("\nFirst few disagreements per field:")
    for f in gs.GOLD_FIELDS:
        ds = metrics[f].disagreements[:3]
        if not ds:
            continue
        print(f"  [{f}]")
        for nid, g, p in ds:
            print(f"    {nid}: gold={g!r}  pred={p!r}")

    baseline = gs.load_baseline(gold_dir)
    drift_regressions: list[tuple[str, float, float]] = []
    if baseline:
        print("\nDrift vs baseline:")
        for f in gs.GOLD_FIELDS:
            b = baseline.get(f)
            if not b:
                continue
            delta = metrics[f].f1 - b["f1"]
            marker = "↑" if delta > 0 else "↓" if delta < 0 else "·"
            print(f"  {f:38s} {marker} {delta:+.3f}  (baseline {b['f1']:.2f})")
            if delta < -args.drift_tolerance:
                drift_regressions.append((f, b["f1"], metrics[f].f1))

    if args.save_baseline:
        gs.save_baseline(gold_dir, metrics)
        print(f"\nBaseline saved to {gs.baseline_path(gold_dir)}")

    if args.check_drift and drift_regressions:
        print(
            f"\nDrift gate FAILED — {len(drift_regressions)} field(s) regressed "
            f"more than {args.drift_tolerance:.2f} from baseline:"
        )
        for f, old, new in drift_regressions:
            print(f"  {f}: {old:.2f} -> {new:.2f}")
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Gold-set sampling, seeding and F1 reporting.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--vault", default=str(REPO_ROOT / "vault"))
    p.add_argument("--gold-dir", default=str(DEFAULT_GOLD_DIR))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("seed", help="Pick stratified sample + write YAML seeds")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--overwrite", action="store_true",
                   help="Re-seed YAMLs even if they exist (DESTROYS reviewer edits)")
    s.set_defaults(func=cmd_seed)

    r = sub.add_parser("report", help="Compare LLM extraction to reviewed gold rows")
    r.add_argument("--save-baseline", action="store_true",
                   help="Save current metrics as the baseline for drift checks")
    r.add_argument("--from-json", default=None,
                   help="Load predictions from a normas.json file instead of "
                        "the vault (use in CI where the vault is not checked in)")
    r.add_argument("--check-drift", action="store_true",
                   help="Exit non-zero if any field's F1 regressed more than "
                        "--drift-tolerance from the saved baseline.")
    r.add_argument("--drift-tolerance", type=float, default=0.05,
                   help="Maximum allowed F1 regression per field (default: 0.05)")
    r.set_defaults(func=cmd_report)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
