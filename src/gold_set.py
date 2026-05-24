"""Phase 2 — gold set primitives.

The gold set is a small (target: 100) collection of norms that a human has
hand-labelled directly from the source legal text. It is the ground truth
against which every later change to the extraction logic, the keyword
vocabulary, or the scoring formula is measured.

Two concerns live here:

  1. **Stratified sampling** — pick a balanced 100-norm sample so the gold
     set covers the diversity of jurisdictions (region), regulatory
     postures (regime) and service complexity (count of `exige_*=true`
     triggers). We do not want all 100 to be MiCA transpositions.

  2. **F1 comparison** — given a YAML gold file and the current LLM
     extraction, compute precision / recall / F1 per field across the
     13 structured signals (regime, status, deadline, seven exige_*,
     plus tipo_deadline, escopo, gap_ou_ambiguidade).

The human workflow lives in scripts/gold.py.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

from . import business_schema as bs


# Fields tracked in the gold set. Order matters for the report layout.
GOLD_FIELDS: tuple[str, ...] = (
    "regime",
    "status_regulatorio",
    "deadline_principal",
    "tipo_deadline",
    "exige_auditoria_tecnica",
    "exige_proof_of_reserves",
    "exige_pentest",
    "exige_kyt_aml",
    "exige_seguranca_custodia",
    "exige_formal_verification",
    "exige_certificacao_independente",
    # Free-form fields are graded "present" vs "absent" only — exact text
    # comparison is hostile, so we score whether both sides agree the
    # signal exists.
    "escopo",
    "gap_ou_ambiguidade",
)

_BINARY_FIELDS = {
    "exige_auditoria_tecnica",
    "exige_proof_of_reserves",
    "exige_pentest",
    "exige_kyt_aml",
    "exige_seguranca_custodia",
    "exige_formal_verification",
    "exige_certificacao_independente",
}

_FREEFORM_FIELDS = {"escopo", "gap_ou_ambiguidade"}


# ---------- Stratified sampling -------------------------------------------


def _stratum_key(extra: dict[str, Any], country: str) -> tuple[str, str, str]:
    """Build a (region, regime, intensity-bucket) tuple so the sampler can
    balance picks across postures and service complexity, not just regions.
    """
    region = bs.REGIONS.get(country, "Other")
    regime = extra.get("regime") or "unknown"
    n_triggers = sum(
        1 for k in bs.SERVICE_TRIGGERS if extra.get(k) is True
    )
    if n_triggers == 0:
        intensity = "0"
    elif n_triggers <= 2:
        intensity = "1-2"
    elif n_triggers <= 4:
        intensity = "3-4"
    else:
        intensity = "5+"
    return (region, regime, intensity)


def stratified_sample(
    candidates: list[tuple[str, str, dict[str, Any]]],
    n: int,
    seed: int = 1729,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Pick `n` norms balanced across (region, regime, intensity).

    candidates: list of (note_id, country, extra-frontmatter).
    Returns a subset deterministically (seeded round-robin across strata).
    """
    import random

    rng = random.Random(seed)

    buckets: dict[tuple[str, str, str], list] = defaultdict(list)
    for item in candidates:
        key = _stratum_key(item[2], item[1])
        buckets[key].append(item)

    # Round-robin across non-empty strata until we hit n. Each round, pick
    # one (shuffled) item from each stratum.
    for ls in buckets.values():
        rng.shuffle(ls)

    picked: list = []
    while len(picked) < n and any(buckets.values()):
        for key in list(buckets.keys()):
            if not buckets[key]:
                continue
            picked.append(buckets[key].pop())
            if len(picked) >= n:
                break
    return picked


# ---------- Comparison ----------------------------------------------------


@dataclass
class FieldMetrics:
    field: str
    tp: int = 0       # both gold and pred agree on a non-null value
    fp: int = 0       # pred claims a value, gold says none / different value
    fn: int = 0       # gold has a value, pred missed it / wrong value
    tn: int = 0       # both agree it's null (only counted for binary)
    disagreements: list[tuple[str, Any, Any]] = None  # (note_id, gold, pred)

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) else 0.0

    @property
    def support(self) -> int:
        return self.tp + self.fn

    def __post_init__(self) -> None:
        if self.disagreements is None:
            self.disagreements = []


def _normalize_value(field: str, v: Any) -> Any:
    """Bring gold and prediction values into a comparable shape."""
    if v in (None, "", "null"):
        return None
    if field in _BINARY_FIELDS:
        if v is True or v in ("True", "true", "1"):
            return True
        if v is False or v in ("False", "false", "0"):
            return False
        return None
    if field in _FREEFORM_FIELDS:
        # collapse to "has content" boolean for grading; exact-text scoring
        # is impractical with free-form summaries.
        if isinstance(v, str) and v.strip():
            return "present"
        return None
    return str(v).strip()


def compare(
    gold: dict[str, dict[str, Any]],
    pred: dict[str, dict[str, Any]],
    fields: Iterable[str] = GOLD_FIELDS,
) -> dict[str, FieldMetrics]:
    """Compute per-field TP / FP / FN / TN against the gold set."""
    out: dict[str, FieldMetrics] = {f: FieldMetrics(f) for f in fields}
    for note_id, gold_row in gold.items():
        pred_row = pred.get(note_id, {})
        for field in fields:
            g = _normalize_value(field, gold_row.get(field))
            p = _normalize_value(field, pred_row.get(field))
            m = out[field]
            if g is None and p is None:
                m.tn += 1
                continue
            if g is not None and p is not None and g == p:
                m.tp += 1
                continue
            if g is None and p is not None:
                m.fp += 1
            elif g is not None and p is None:
                m.fn += 1
            else:
                # Different non-null values count as both FP and FN.
                m.fp += 1
                m.fn += 1
            m.disagreements.append((note_id, gold_row.get(field), pred_row.get(field)))
    return out


def overall_f1(metrics: dict[str, FieldMetrics]) -> float:
    """Macro-average F1 across fields, weighted by support."""
    weighted_sum = 0.0
    total_support = 0
    for m in metrics.values():
        if m.support == 0:
            continue
        weighted_sum += m.f1 * m.support
        total_support += m.support
    return weighted_sum / total_support if total_support else 0.0


# ---------- YAML I/O ------------------------------------------------------


def load_gold_dir(path: Path) -> dict[str, dict[str, Any]]:
    """Load every `<note_id>.yaml` from a directory whose top-level
    `reviewed:` flag is true. Files marked `reviewed: false` are ignored
    (treated as drafts).
    """
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for p in sorted(path.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if not data.get("reviewed"):
            continue
        nid = data.get("id") or p.stem
        out[nid] = data
    return out


def dump_seed(path: Path, payload: dict[str, Any]) -> None:
    """Write a seed YAML file. The payload includes the current LLM
    extraction so the labeller's task is review-and-correct, not annotate
    from scratch.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def baseline_path(gold_dir: Path) -> Path:
    return gold_dir / "_baseline.json"


def save_baseline(gold_dir: Path, metrics: dict[str, FieldMetrics]) -> None:
    rows = {
        f: {
            "tp": m.tp, "fp": m.fp, "fn": m.fn, "tn": m.tn,
            "precision": round(m.precision, 4),
            "recall": round(m.recall, 4),
            "f1": round(m.f1, 4),
            "support": m.support,
        }
        for f, m in metrics.items()
    }
    baseline_path(gold_dir).write_text(
        json.dumps(rows, indent=2, sort_keys=False),
        encoding="utf-8",
    )


def load_baseline(gold_dir: Path) -> Optional[dict[str, dict[str, float]]]:
    p = baseline_path(gold_dir)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
