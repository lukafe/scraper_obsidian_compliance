"""Smoke tests for Phase 3 validators.

Covers:
  - supports_obligation: imperative-verb check across EN, PT, ES, FR, DE
  - supports_deadline:   date + temporal-keyword combo
  - supports_regime:     regime vocabulary by enum value
  - keyword_hits:        word-boundary, short-token, phrase matching
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.validators import (  # noqa: E402
    supports_obligation,
    supports_deadline,
    supports_regime,
    keyword_hits,
)


def _check(label: str, got: bool, want: bool) -> bool:
    status = "PASS" if got == want else "FAIL"
    print(f"  {status} {label}  (got={got}, want={want})")
    return got == want


def main() -> int:
    print("=== Phase 3 — validator smoke tests ===\n")
    passed = True

    # ---- supports_obligation -----------------------------------------
    print("[supports_obligation]")
    passed &= _check(
        "EN: 'shall' present",
        supports_obligation("Providers shall perform an annual penetration test."),
        True,
    )
    passed &= _check(
        "EN: 'must be performed annually'",
        supports_obligation("A red-team exercise must be performed annually."),
        True,
    )
    passed &= _check(
        "PT: 'deverá'",
        supports_obligation("A entidade deverá realizar testes de invasão."),
        True,
    )
    passed &= _check(
        "ES: 'debe'",
        supports_obligation("El proveedor debe someter sus sistemas a una prueba de penetración."),
        True,
    )
    passed &= _check(
        "FR: 'doivent'",
        supports_obligation("Les prestataires doivent effectuer un test d'intrusion annuel."),
        True,
    )
    passed &= _check(
        "DE: 'müssen'",
        supports_obligation("Anbieter müssen einen jährlichen Penetrationstest durchführen."),
        True,
    )
    passed &= _check(
        "Descriptive recital — no imperative",
        supports_obligation("Penetration testing is a common industry practice."),
        False,
    )
    passed &= _check(
        "Empty evidence",
        supports_obligation(""),
        False,
    )
    passed &= _check(
        "None evidence",
        supports_obligation(None),
        False,
    )

    # ---- supports_deadline -------------------------------------------
    print("\n[supports_deadline]")
    passed &= _check(
        "EN: by + date",
        supports_deadline("2025-12-31", "Compliance must be achieved by 2025-12-31."),
        True,
    )
    passed &= _check(
        "EN: transitional + year",
        supports_deadline("2025-12-31", "The transitional period expires in 2025."),
        True,
    )
    passed &= _check(
        "PT: até + data",
        supports_deadline("2024-06-30", "Os prestadores deverão se adequar até 2024-06-30."),
        True,
    )
    passed &= _check(
        "DE: spätestens + year",
        supports_deadline("2025-06-30", "Die Anpassung ist spätestens 2025 vorzunehmen."),
        True,
    )
    passed &= _check(
        "Date appears but no temporal anchor",
        supports_deadline("2025-12-31", "Resolution 2025-12-31 was reviewed by the board."),
        False,
    )
    passed &= _check(
        "Date not in quote",
        supports_deadline("2025-12-31", "Compliance must be achieved by the deadline."),
        False,
    )
    passed &= _check(
        "No date",
        supports_deadline(None, "Compliance must be achieved by 2025-12-31."),
        False,
    )

    # ---- supports_regime ---------------------------------------------
    print("\n[supports_regime]")
    passed &= _check(
        "licenciamento + 'license'",
        supports_regime("licenciamento", "Providers must obtain a license from BaFin."),
        True,
    )
    passed &= _check(
        "licenciamento + 'authorisation'",
        supports_regime("licenciamento", "Prior authorisation by the FCA is required."),
        True,
    )
    passed &= _check(
        "licenciamento + PT 'autorização'",
        supports_regime("licenciamento", "É necessária autorização prévia do BCB."),
        True,
    )
    passed &= _check(
        "licenciamento + DE 'Genehmigung'",
        supports_regime("licenciamento", "Die Genehmigung der BaFin ist erforderlich."),
        True,
    )
    passed &= _check(
        "registro + 'registration'",
        supports_regime("registro", "VASPs are subject to a registration regime."),
        True,
    )
    passed &= _check(
        "proibicao + 'prohibited'",
        supports_regime("proibicao", "Crypto-asset trading is prohibited for residents."),
        True,
    )
    passed &= _check(
        "em_consulta + 'consultation'",
        supports_regime("em_consulta", "The draft is open for public consultation until June."),
        True,
    )
    passed &= _check(
        "licenciamento BUT quote talks about registration",
        supports_regime("licenciamento", "Only a simple registration with the regulator is needed."),
        False,
    )
    passed &= _check(
        "desconhecido — no semantic check",
        supports_regime("desconhecido", "Anything goes here."),
        True,
    )

    # ---- keyword_hits ------------------------------------------------
    print("\n[keyword_hits]")
    passed &= _check(
        "Phrase 'travel rule' matches",
        bool(keyword_hits("The travel rule applies to VASPs.", ["travel rule"])),
        True,
    )
    passed &= _check(
        "Word-boundary: 'aml' must NOT match inside 'examined'",
        bool(keyword_hits(
            "The notice was examined by the regulator.",
            ["aml"],
        )),
        False,
    )
    passed &= _check(
        "Word-boundary: 'aml' DOES match as a standalone token",
        bool(keyword_hits("AML controls are required.", ["aml"])),
        True,
    )
    passed &= _check(
        "Short non-whitelisted token gets dropped",
        bool(keyword_hits("the quick brown fox", ["fox"])),
        False,  # 'fox' is 3 chars and not whitelisted
    )
    passed &= _check(
        "Long token matches with boundary",
        bool(keyword_hits("Annual penetration test is required.", ["penetration"])),
        True,
    )
    passed &= _check(
        "Long token does NOT match inside a larger word",
        bool(keyword_hits("Pentecost is a Christian holiday.", ["pentest"])),
        False,
    )
    passed &= _check(
        "Empty text returns empty",
        bool(keyword_hits("", ["pentest"])),
        False,
    )

    print()
    if passed:
        print("All Phase 3 validator smoke tests PASSED.")
        return 0
    print("Some Phase 3 validator smoke tests FAILED.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
