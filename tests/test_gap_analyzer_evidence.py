"""Smoke tests for the Phase 1 evidence-trail enforcement.

Exercises gap_analyzer._normalize_findings directly with synthetic LLM
output so we never spend tokens. The contract under test:

    if quote is verbatim substring of body  -> field + evidence retained
    if quote is paraphrase / fabricated     -> both demoted to None
    if quote is missing for non-null field  -> both demoted to None
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.gap_analyzer import _normalize_findings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")


BODY = (
    "Article 5. Crypto-asset service providers shall obtain prior "
    "authorization from BaFin before commencing operations. Penetration "
    "testing must be performed annually by an independent third party. "
    "The transitional period ends on 2025-12-31."
)


def _run(case: str, raw: dict, expected: dict) -> bool:
    out = _normalize_findings(raw, body=BODY, note_id="TEST")
    ok = True
    for key, want in expected.items():
        got = out.get(key)
        if got != want:
            print(f"  FAIL {case} :: {key} expected={want!r} got={got!r}")
            ok = False
    if ok:
        print(f"  PASS {case}")
    return ok


def main() -> int:
    print("=== Phase 1 — evidence trail smoke tests ===\n")
    passed = True

    # 1. Verbatim quote — both should land.
    passed &= _run(
        "verbatim regime",
        {
            "regime": "licenciamento",
            "regime_evidence": "shall obtain prior authorization from BaFin",
            "exige_pentest": True,
            "exige_pentest_evidence": (
                "Penetration testing must be performed annually by an "
                "independent third party"
            ),
            "deadline_principal": "2025-12-31",
            "deadline_principal_evidence": "transitional period ends on 2025-12-31",
        },
        {
            "regime": "licenciamento",
            "regime_evidence": "shall obtain prior authorization from BaFin",
            "exige_pentest": True,
            "deadline_principal": "2025-12-31",
        },
    )

    # 2. Paraphrase that the model would have invented — gets demoted.
    passed &= _run(
        "fabricated regime quote",
        {
            "regime": "licenciamento",
            "regime_evidence": "providers need a license to operate",  # NOT in body
        },
        {
            "regime": None,
            "regime_evidence": None,
        },
    )

    # 3. Missing evidence entirely — non-null field also demoted.
    passed &= _run(
        "missing evidence",
        {
            "exige_proof_of_reserves": True,
            # no exige_proof_of_reserves_evidence key
        },
        {
            "exige_proof_of_reserves": None,
            "exige_proof_of_reserves_evidence": None,
        },
    )

    # 4. Quote too short — demoted.
    passed &= _run(
        "too-short quote",
        {
            "regime": "licenciamento",
            "regime_evidence": "BaFin",
        },
        {
            "regime": None,
            "regime_evidence": None,
        },
    )

    # 5. Null field — evidence collapses to None even if model returned one.
    passed &= _run(
        "null field + stray evidence",
        {
            "regime": None,
            "regime_evidence": "shall obtain prior authorization from BaFin",
        },
        {
            "regime": None,
            "regime_evidence": None,
        },
    )

    # 6. Whitespace tolerance — newline-collapsed quote still validates.
    passed &= _run(
        "whitespace-tolerant",
        {
            "status_regulatorio": "vigente",
            "status_regulatorio_evidence": (
                "Crypto-asset service providers   shall obtain prior\n"
                "authorization from BaFin"
            ),
        },
        {
            "status_regulatorio": "vigente",
        },
    )

    # 7. Free-form fields (escopo) are exempt — no evidence required.
    passed &= _run(
        "free-form escopo passes through",
        {
            "escopo": "Sets BaFin authorization regime for CASPs.",
        },
        {
            "escopo": "Sets BaFin authorization regime for CASPs.",
        },
    )

    print()
    if passed:
        print("All smoke tests PASSED.")
        return 0
    print("Some smoke tests FAILED.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
