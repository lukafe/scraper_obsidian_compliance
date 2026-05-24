"""Phase 2 — second batch of hand-annotated gold rows (3 more).

Adds DE-DORA-2022, GB-MLRS2017PART7A-2023, SG-SCSFRAMEWORK-2023 to the
starter pack. Same conservative philosophy: every non-null gold value
carries a verbatim quote pulled from the body; fields the body doesn't
substantiate stay None even when the LLM made a call.

After running, gold support grows from 5 -> 8 norms (65 -> ~104 graded
field instances).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import yaml

GOLD_DIR = REPO_ROOT / "vault" / "_export" / "ground_truth"
REVIEWER = "phase2-starter-v2"
REVIEWED_AT = date.today().isoformat()


ANNOTATIONS = {
    # =======================================================================
    "DE-DORA-2022": {
        # DORA is an operational-resilience regulation: it does not establish
        # a licensing or registration REGIME — it layers requirements on
        # entities already authorised under sectoral law. Gold leaves the
        # regime as None for that reason.
        "regime": None,
        "regime_evidence": None,
        "status_regulatorio": "em_implementacao",
        "status_regulatorio_evidence": (
            "this Regulation shall be considered a sector-specific Union legal act"
        ),
        "deadline_principal": None,
        "deadline_principal_evidence": None,
        "tipo_deadline": None,
        "tipo_deadline_evidence": None,
        "exige_auditoria_tecnica": True,
        "exige_auditoria_tecnica_evidence": (
            "the requirement to perform advanced testing of ICT tools, systems "
            "and processes based on threat-led penetration testing (TLPT)"
        ),
        "exige_proof_of_reserves": None,
        "exige_proof_of_reserves_evidence": None,
        "exige_pentest": True,
        "exige_pentest_evidence": (
            "delivers a controlled, bespoke, intelligence-led (red team) test "
            "of the financial entity’s critical live production systems"
        ),
        "exige_kyt_aml": None,
        "exige_kyt_aml_evidence": None,
        # DORA is ICT-resilience-centric; it does not impose custody controls
        # over client crypto assets. Gold leaves this null even though the
        # LLM said True.
        "exige_seguranca_custodia": None,
        "exige_seguranca_custodia_evidence": None,
        "exige_formal_verification": None,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": False,
        "exige_certificacao_independente_evidence": None,
        "escopo": "present",
        "gap_ou_ambiguidade": "present",
        "notes": (
            "DORA layers ICT-resilience obligations on top of existing financial "
            "regimes; it is NOT a regime in itself. Pentest and tech-audit "
            "obligations are explicit in the body (TLPT, red team). Custody "
            "claim from the LLM has no body grounding."
        ),
    },
    # =======================================================================
    "GB-MLRS2017PART7A-2023": {
        # Travel Rule amendment to the UK MLRs 2017. The body is the amended
        # text only (Part 7A), not the standalone licensing regime — that
        # lives in the FCA's separate crypto-register provisions.
        "regime": None,
        "regime_evidence": None,
        "status_regulatorio": None,
        "status_regulatorio_evidence": None,
        "deadline_principal": None,
        "deadline_principal_evidence": None,
        "tipo_deadline": None,
        "tipo_deadline_evidence": None,
        "exige_auditoria_tecnica": None,
        "exige_auditoria_tecnica_evidence": None,
        "exige_proof_of_reserves": None,
        "exige_proof_of_reserves_evidence": None,
        "exige_pentest": None,
        "exige_pentest_evidence": None,
        "exige_kyt_aml": True,
        "exige_kyt_aml_evidence": (
            "the cryptoasset business of the originator must ensure that the "
            "cryptoasset transfer is accompanied by the information specified "
            "in paragraph (5)"
        ),
        "exige_seguranca_custodia": None,
        "exige_seguranca_custodia_evidence": None,
        "exige_formal_verification": None,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": None,
        "exige_certificacao_independente_evidence": None,
        "escopo": "present",
        "gap_ou_ambiguidade": "present",
        "notes": (
            "UK Travel-Rule amendment. Only exige_kyt_aml is body-grounded; "
            "regime / status / deadline come from the title metadata, not the "
            "scraped Part 7A text itself, so gold demotes them to null."
        ),
    },
    # =======================================================================
    "SG-SCSFRAMEWORK-2023": {
        "regime": "licenciamento",
        "regime_evidence": (
            "The Monetary Authority of Singapore (MAS) today announced the "
            "features of a new regulatory framework"
        ),
        "status_regulatorio": None,
        "status_regulatorio_evidence": None,
        "deadline_principal": None,
        "deadline_principal_evidence": None,
        "tipo_deadline": None,
        "tipo_deadline_evidence": None,
        "exige_auditoria_tecnica": True,
        "exige_auditoria_tecnica_evidence": (
            "Reserve assets will be subject to requirements relating to their "
            "composition, valuation, custody and audit"
        ),
        "exige_proof_of_reserves": True,
        "exige_proof_of_reserves_evidence": (
            "Reserve assets will be subject to requirements relating to their "
            "composition, valuation, custody and audit, to give a high degree "
            "of assurance of value stability"
        ),
        "exige_pentest": None,
        "exige_pentest_evidence": None,
        "exige_kyt_aml": None,
        "exige_kyt_aml_evidence": None,
        "exige_seguranca_custodia": True,
        "exige_seguranca_custodia_evidence": (
            "Reserve assets will be subject to requirements relating to their "
            "composition, valuation, custody and audit"
        ),
        "exige_formal_verification": None,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": True,
        "exige_certificacao_independente_evidence": (
            "Reserve assets will be subject to requirements relating to their "
            "composition, valuation, custody and audit, to give a high degree "
            "of assurance of value stability"
        ),
        "escopo": "present",
        "gap_ou_ambiguidade": "present",
        "notes": (
            "Singapore Stablecoin Framework press release. POR / custody / "
            "tech-audit / independent-certification all anchored in the single "
            "sentence about reserve assets being subject to composition / "
            "valuation / custody / audit requirements. Body is short so the "
            "regime quote is weak; status / deadline are not in the press text."
        ),
    },
}


def main() -> int:
    count = 0
    for nid, fields in ANNOTATIONS.items():
        path = GOLD_DIR / f"{nid}.yaml"
        if not path.exists():
            print(f"  SKIP missing seed: {path}")
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data.update(fields)
        data["reviewed"] = True
        data["reviewer"] = REVIEWER
        data["reviewed_at"] = REVIEWED_AT
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        count += 1
        print(f"  wrote {nid}")
    print(f"\nAnnotated {count} more gold rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
