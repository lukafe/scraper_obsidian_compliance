"""Phase 4 — smoke tests for coverage detection and maturity mapping."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coverage import (  # noqa: E402
    detect_norm_coverage,
    aggregate_coverage,
    maturity_from_coverage,
)


def _check(label: str, got, want) -> bool:
    status = "PASS" if got == want else "FAIL"
    print(f"  {status} {label}  got={got} want={want}")
    return got == want


def main() -> int:
    print("=== Phase 4 — coverage smoke tests ===\n")
    passed = True

    # detect_norm_coverage from boolean triggers
    print("[detect_norm_coverage — boolean triggers]")
    passed &= _check(
        "exige_kyt_aml=True implies aml",
        detect_norm_coverage({"exige_kyt_aml": True}),
        {"aml"},
    )
    passed &= _check(
        "exige_seguranca_custodia=True implies custody",
        detect_norm_coverage({"exige_seguranca_custodia": True}),
        {"custody"},
    )

    # detect_norm_coverage from escopo keywords (with word boundaries)
    print("\n[detect_norm_coverage — escopo keywords]")
    passed &= _check(
        "escopo mentions whitepaper -> issuance",
        detect_norm_coverage({"escopo": "Issuers must publish a whitepaper before any offering."}),
        {"issuance"},
    )
    passed &= _check(
        "escopo mentions custody + AML -> both",
        detect_norm_coverage({
            "escopo": "Custodians shall implement KYC and KYT controls.",
        }),
        {"custody", "aml"},
    )
    passed &= _check(
        "escopo mentions market manipulation -> market_abuse",
        detect_norm_coverage({
            "escopo": "The rule prohibits market manipulation and insider dealing.",
        }),
        {"market_abuse"},
    )
    passed &= _check(
        "escopo mentions retail investor disclosure -> consumer_protection",
        detect_norm_coverage({
            "escopo": "Issuers must provide disclosure aimed at retail investors.",
        }),
        {"consumer_protection"},
    )
    passed &= _check(
        "escopo mentions capital gains tax -> taxation",
        detect_norm_coverage({
            "escopo": "Capital gains from crypto transactions are subject to income tax.",
        }),
        {"taxation"},
    )

    # Empty / unrelated escopo -> no false positive
    print("\n[no false positives]")
    passed &= _check(
        "Unrelated escopo about agriculture -> empty",
        detect_norm_coverage({"escopo": "This decree regulates fertiliser imports."}),
        set(),
    )
    passed &= _check(
        "'aml' as substring of 'examined' must NOT match",
        detect_norm_coverage({"escopo": "The proposal was examined by experts."}),
        set(),
    )

    # Phase 1 evidence quotes are also scanned
    print("\n[Phase 1 evidence quotes]")
    passed &= _check(
        "regime_evidence with 'authorisation' triggers no dimension by itself",
        detect_norm_coverage({"regime_evidence": "Prior authorisation by BaFin is required."}),
        set(),
    )
    passed &= _check(
        "exige_pentest_evidence with 'custody' triggers custody dimension",
        detect_norm_coverage({
            "exige_pentest_evidence": (
                "Custodians shall perform an annual penetration test of their custody systems."
            ),
        }),
        {"custody"},
    )

    # aggregate_coverage — OR over norms
    print("\n[aggregate_coverage]")
    passed &= _check(
        "Union of three norms",
        aggregate_coverage([
            {"escopo": "Whitepaper requirement for token offerings."},
            {"exige_kyt_aml": True},
            {"escopo": "Capital gains tax applies."},
        ]),
        {"issuance", "aml", "taxation"},
    )

    # maturity_from_coverage
    print("\n[maturity_from_coverage]")
    passed &= _check("0 -> desconhecido", maturity_from_coverage(set()), "desconhecido")
    passed &= _check("1 -> baixa", maturity_from_coverage({"aml"}), "baixa")
    passed &= _check("2 -> baixa", maturity_from_coverage({"aml", "custody"}), "baixa")
    passed &= _check("3 -> media", maturity_from_coverage({"aml", "custody", "taxation"}), "media")
    passed &= _check(
        "4 -> media",
        maturity_from_coverage({"aml", "custody", "taxation", "issuance"}),
        "media",
    )
    passed &= _check(
        "5 -> alta",
        maturity_from_coverage(
            {"aml", "custody", "taxation", "issuance", "market_abuse"},
        ),
        "alta",
    )
    passed &= _check(
        "6 -> alta",
        maturity_from_coverage(
            {"aml", "custody", "taxation", "issuance", "market_abuse", "consumer_protection"},
        ),
        "alta",
    )

    print()
    if passed:
        print("All Phase 4 coverage smoke tests PASSED.")
        return 0
    print("Some Phase 4 coverage smoke tests FAILED.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
