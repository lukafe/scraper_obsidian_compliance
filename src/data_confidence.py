"""Phase 5 — per-jurisdiction data-confidence scoring.

The opportunity score answers "how attractive is this market?". This
module answers a different question: "how much should the decision-maker
trust that answer?".

A 0-100 confidence score per jurisdiction, computed from four orthogonal
signals — all derived from the existing vault state, no LLM cost:

    1. Analysis coverage   (35%)  n_analyzed / n_total
    2. Coverage breadth    (25%)  n_cobertura / 6
    3. Regulator diversity (15%)  1 - 1/(1 + n_distinct_regulators)
    4. Evidence density    (25%)  share of norms whose Phase-1 evidence
                                  fields are populated. Currently 0 across
                                  the vault — it lights up as the gap
                                  analyzer is rerun with the Phase-1
                                  prompt.

The weights add up to 1. Each component is normalized to [0, 1] and the
final score is rounded to one decimal in [0, 100].

The score is intentionally NOT used to gate the opportunity ranking —
it sits alongside as a separate transparency signal so the dashboard
can warn "this score is built on thin data" without quietly demoting
the country.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


# Weights — kept here so a future calibration can tune them in one place.
W_ANALYSIS = 0.35
W_COVERAGE = 0.25
W_REGULATORS = 0.15
W_EVIDENCE = 0.25
assert abs(W_ANALYSIS + W_COVERAGE + W_REGULATORS + W_EVIDENCE - 1.0) < 1e-9


# Phase-1 evidence fields — must stay in sync with src/business_schema.EVIDENCE_FIELDS.
_EVIDENCE_FIELDS: tuple[str, ...] = (
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
)


def _evidence_density_for_norm(extra: dict[str, Any]) -> Optional[float]:
    """Among the structured fields that the analyzer extracted a non-null
    value for, what fraction also carry a verbatim evidence quote? Returns
    None for norms with no extracted values — those are excluded from the
    jurisdiction-level average so they cannot inflate it.
    """
    populated = 0
    with_evidence = 0
    for f in _EVIDENCE_FIELDS:
        if extra.get(f) is None:
            continue
        populated += 1
        if extra.get(f"{f}_evidence"):
            with_evidence += 1
    if populated == 0:
        return None
    return with_evidence / populated


def evidence_density(norms: Iterable[dict[str, Any]]) -> float:
    """Average evidence density across a jurisdiction's norms that have at
    least one extracted structured field. If no norm has any extractions
    the jurisdiction has no claims to substantiate => 0.0.
    """
    densities = [d for d in (_evidence_density_for_norm(e) for e in norms)
                 if d is not None]
    if not densities:
        return 0.0
    return sum(densities) / len(densities)


def regulator_diversity(n_distinct: int) -> float:
    """1 - 1/(1 + n) maps {0, 1, 2, 3, 4, 5} -> {0.0, 0.5, 0.67, 0.75, 0.8, 0.83}."""
    return 1.0 - 1.0 / (1.0 + max(0, n_distinct))


def confidence_score(
    *,
    n_total: int,
    n_analyzed: int,
    n_cobertura: int,
    n_distinct_regulators: int,
    evidence_density_value: float,
) -> float:
    """Combine the four signals into a 0-100 confidence score."""
    analysis = (n_analyzed / n_total) if n_total else 0.0
    coverage = (n_cobertura / 6) if n_cobertura is not None else 0.0
    regulators = regulator_diversity(n_distinct_regulators)
    blended = (
        W_ANALYSIS * analysis
        + W_COVERAGE * coverage
        + W_REGULATORS * regulators
        + W_EVIDENCE * max(0.0, min(1.0, evidence_density_value))
    )
    return round(100 * blended, 1)


def confidence_tier(score: float) -> str:
    """Human-facing tier label for a confidence score."""
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def compute_jurisdiction_confidence(
    *,
    norms_extras: list[dict[str, Any]],
    n_total: int,
    n_analyzed: int,
    n_cobertura: int,
    n_distinct_regulators: int,
) -> dict[str, Any]:
    """High-level entry point — what overviews.upsert_overview calls.

    Returns a dict with the score, the tier, and the four components so
    the dashboard can explain WHY a country is high/medium/low confidence.
    """
    ed = evidence_density(norms_extras)
    score = confidence_score(
        n_total=n_total,
        n_analyzed=n_analyzed,
        n_cobertura=n_cobertura,
        n_distinct_regulators=n_distinct_regulators,
        evidence_density_value=ed,
    )
    return {
        "score": score,
        "tier": confidence_tier(score),
        "components": {
            "analysis_coverage": round((n_analyzed / n_total) if n_total else 0.0, 3),
            "coverage_breadth": round((n_cobertura / 6) if n_cobertura else 0.0, 3),
            "regulator_diversity": round(regulator_diversity(n_distinct_regulators), 3),
            "evidence_density": round(ed, 3),
        },
    }
