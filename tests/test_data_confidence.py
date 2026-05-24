"""Phase 5 — data-confidence formula smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.data_confidence import (  # noqa: E402
    confidence_score,
    confidence_tier,
    evidence_density,
    regulator_diversity,
    compute_jurisdiction_confidence,
)


def _check(label: str, got, want, tol: float = 0.05) -> bool:
    ok = abs((got or 0) - (want or 0)) <= tol if isinstance(got, (int, float)) else got == want
    status = "PASS" if ok else "FAIL"
    print(f"  {status} {label}  got={got!r} want={want!r}")
    return ok


def main() -> int:
    print("=== Phase 5 — data-confidence smoke tests ===\n")
    passed = True

    # regulator_diversity is a saturating curve.
    print("[regulator_diversity]")
    passed &= _check("0 regulators -> 0.0", regulator_diversity(0), 0.0)
    passed &= _check("1 regulator -> 0.5", regulator_diversity(1), 0.5)
    passed &= _check("3 regulators -> 0.75", regulator_diversity(3), 0.75)
    passed &= _check("10 regulators -> ~0.91", regulator_diversity(10), 0.909)

    # evidence_density — when no Phase-1 evidence is populated, every norm
    # scores 1.0 (nothing to substantiate yet). When some are populated,
    # the ratio counts.
    print("\n[evidence_density]")
    passed &= _check(
        "empty -> 0.0",
        evidence_density([]),
        0.0,
    )
    passed &= _check(
        "all-null fields excluded -> 0.0 (no claims to substantiate)",
        evidence_density([{"regime": None, "exige_pentest": None}]),
        0.0,
    )
    passed &= _check(
        "mix of all-null + half-evidenced norms -> 0.5",
        evidence_density([
            {"regime": None},  # skipped — no claim
            {"regime": "licenciamento", "regime_evidence": "..."},   # 1/1
            {"regime": "registro", "regime_evidence": None},          # 0/1
        ]),
        0.5,
    )
    passed &= _check(
        "fully evidenced -> 1.0",
        evidence_density([{
            "regime": "licenciamento",
            "regime_evidence": "the provider shall obtain a license",
            "exige_kyt_aml": True,
            "exige_kyt_aml_evidence": "AML rules apply",
        }]),
        1.0,
    )
    passed &= _check(
        "half-evidenced -> 0.5",
        evidence_density([{
            "regime": "licenciamento",
            "regime_evidence": "the provider shall obtain a license",
            "exige_kyt_aml": True,
            "exige_kyt_aml_evidence": None,
        }]),
        0.5,
    )
    passed &= _check(
        "two norms average",
        evidence_density([
            {"regime": "licenciamento", "regime_evidence": "..."},   # 1/1
            {"regime": "registro", "regime_evidence": None},          # 0/1
        ]),
        0.5,
    )

    # confidence_score sanity: high-signal market saturates around 90+.
    print("\n[confidence_score]")
    high = confidence_score(
        n_total=50, n_analyzed=50,
        n_cobertura=6, n_distinct_regulators=5,
        evidence_density_value=1.0,
    )
    passed &= _check("max-signal jurisdiction >= 90", high >= 90, True)

    low = confidence_score(
        n_total=5, n_analyzed=1,
        n_cobertura=0, n_distinct_regulators=0,
        evidence_density_value=0.0,
    )
    passed &= _check("min-signal jurisdiction <= 15", low <= 15, True)

    mid = confidence_score(
        n_total=20, n_analyzed=10,
        n_cobertura=3, n_distinct_regulators=2,
        evidence_density_value=0.5,
    )
    passed &= _check("balanced -> 45-65 range", 45 <= mid <= 65, True)

    # tier mapping
    print("\n[confidence_tier]")
    passed &= _check(">= 70 -> high", confidence_tier(70), "high")
    passed &= _check(">= 45 -> medium", confidence_tier(60), "medium")
    passed &= _check("< 45 -> low", confidence_tier(30), "low")

    # End-to-end shape
    print("\n[compute_jurisdiction_confidence]")
    res = compute_jurisdiction_confidence(
        norms_extras=[{}],
        n_total=10, n_analyzed=8,
        n_cobertura=4, n_distinct_regulators=2,
    )
    passed &= _check("returns score key", "score" in res, True)
    passed &= _check("returns tier key", "tier" in res, True)
    passed &= _check("returns 4 components", set(res["components"]) == {
        "analysis_coverage", "coverage_breadth",
        "regulator_diversity", "evidence_density",
    }, True)

    print()
    if passed:
        print("All Phase 5 data-confidence smoke tests PASSED.")
        return 0
    print("Some Phase 5 data-confidence smoke tests FAILED.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
