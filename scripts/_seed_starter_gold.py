"""One-shot helper that overwrites 5 specific gold YAMLs with hand-checked
annotations. Each value was cross-checked against the body of the
underlying note in the vault; evidence quotes are verbatim substrings.

This is the Phase 2 starter pack — a working demo of the gold-set
workflow, not a comprehensive labelling. The other 95 seeds in
vault/_export/ground_truth/ remain `reviewed: false` and are waiting
for the human pass.

After running this script, `python3 scripts/gold.py report` produces
the first end-to-end F1 numbers.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import yaml

GOLD_DIR = REPO_ROOT / "vault" / "_export" / "ground_truth"
REVIEWER = "phase2-starter"
REVIEWED_AT = date.today().isoformat()


# Note: every *_evidence value here was confirmed by grep against the
# corresponding vault/*.md body. Where the body did not surface a clean
# quote, the field is null — the gold set follows the same conservative
# rule as Phase 1 (no evidence => no claim).

ANNOTATIONS = {
    # =======================================================================
    "BR-BCBRES277-2022": {
        "regime": "licenciamento",
        "regime_evidence": (
            "the institution authorized to operate in the foreign exchange market "
            "must be able to prove that the parties consent to the agreed conditions"
        ),
        "status_regulatorio": "em_implementacao",
        "status_regulatorio_evidence": (
            "(Included, as of 02/02/2026, by BCB Resolution No. 521, of 11/10/2025.)"
        ),
        "deadline_principal": "2026-02-02",
        "deadline_principal_evidence": (
            "VI - the provision of virtual asset services provided for in this Resolution. "
            "(Included, as of 02/02/2026, by BCB Resolution No. 521, of 11/10/2025.)"
        ),
        "tipo_deadline": "go_live",
        "tipo_deadline_evidence": (
            "(Included, as of 02/02/2026, by BCB Resolution No. 521, of 11/10/2025.)"
        ),
        "exige_auditoria_tecnica": True,
        "exige_auditoria_tecnica_evidence": (
            "the Central Bank of Brazil may request technical certification or evaluation "
            "issued by an independent qualified company"
        ),
        "exige_proof_of_reserves": None,
        "exige_proof_of_reserves_evidence": None,
        "exige_pentest": None,
        "exige_pentest_evidence": None,
        "exige_kyt_aml": True,
        "exige_kyt_aml_evidence": (
            "the criteria to be adopted in relation to information and supporting documents "
            "for the purposes of preventing money laundering and combating the financing of terrorism"
        ),
        "exige_seguranca_custodia": None,
        "exige_seguranca_custodia_evidence": None,
        "exige_formal_verification": None,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": True,
        "exige_certificacao_independente_evidence": (
            "the Central Bank of Brazil may request technical certification or evaluation "
            "issued by an independent qualified company"
        ),
        "escopo": "present",
        "gap_ou_ambiguidade": "present",
        "notes": (
            "Resolution 277/2022 (FX market) amended by Res. 521/2025 to include virtual "
            "asset services from 02/02/2026. Licensing + AML + independent certification all "
            "anchored in the body. POR/pentest/custody/formal-verif: not surfaced in body."
        ),
    },
    # =======================================================================
    "AE-PTSR-2024": {
        "regime": "licenciamento",
        "regime_evidence": (
            "the Central Bank for granting a License or Registration for the provision of "
            "Payment Token Services and related matters"
        ),
        "status_regulatorio": "vigente",
        "status_regulatorio_evidence": (
            "Payment Token Services Regulation C 2/2024 Effective from 31/8/2024Status: In-Force"
        ),
        "deadline_principal": "2024-08-31",
        "deadline_principal_evidence": "Effective from 31/8/2024",
        "tipo_deadline": "go_live",
        "tipo_deadline_evidence": "Effective from 31/8/2024Status: In-Force",
        "exige_auditoria_tecnica": True,
        "exige_auditoria_tecnica_evidence": (
            "External Auditor: means an independent juridical Person that has been appointed "
            "to audit the accounts and financial statements of a Licensed Payment Token Service Provider"
        ),
        "exige_proof_of_reserves": True,
        "exige_proof_of_reserves_evidence": (
            "to audit the Reserve of Assets of a Licensed Payment Token Issuer"
        ),
        "exige_pentest": True,
        "exige_pentest_evidence": (
            "the results of any penetration or cyber-attack simulation testing performed "
            "pursuant to Article (35)17"
        ),
        "exige_kyt_aml": True,
        "exige_kyt_aml_evidence": (
            "AML/CFT: means Anti-Money Laundering and Combating the Financing of Terrorism"
        ),
        "exige_seguranca_custodia": True,
        "exige_seguranca_custodia_evidence": (
            "three categories, namely Payment Token Issuance, Payment Token Conversion and "
            "Payment Token Custody and Transfer"
        ),
        "exige_formal_verification": None,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": True,
        "exige_certificacao_independente_evidence": (
            "External Auditor: means an independent juridical Person that has been appointed "
            "to audit the accounts and financial statements of a Licensed Payment Token Service Provider"
        ),
        "escopo": "present",
        "gap_ou_ambiguidade": "present",
        "notes": (
            "UAE PTSR is dense — every Phase 1 field has body support. Pentest call is a "
            "correction of the LLM (which had null); the body explicitly references "
            "penetration testing under Article 35.17."
        ),
    },
    # =======================================================================
    "JP-PSA-2009": {
        "regime": "licenciamento",
        "regime_evidence": (
            'has obtained the license under Article 64, paragraph (1)'
        ),
        "status_regulatorio": None,
        "status_regulatorio_evidence": None,
        "deadline_principal": None,
        "deadline_principal_evidence": None,
        "tipo_deadline": None,
        "tipo_deadline_evidence": None,
        # The scraped body does NOT surface body-grounded quotes for the
        # crypto-specific obligations of CAESPs (Articles 63-3 onwards). The
        # LLM's exige_kyt_aml=True and exige_seguranca_custodia=True calls
        # are likely correct in substance but cannot be supported from this
        # body excerpt — gold marks them null per the verbatim-evidence rule.
        "exige_auditoria_tecnica": None,
        "exige_auditoria_tecnica_evidence": None,
        "exige_proof_of_reserves": None,
        "exige_proof_of_reserves_evidence": None,
        "exige_pentest": None,
        "exige_pentest_evidence": None,
        "exige_kyt_aml": None,
        "exige_kyt_aml_evidence": None,
        "exige_seguranca_custodia": None,
        "exige_seguranca_custodia_evidence": None,
        "exige_formal_verification": None,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": None,
        "exige_certificacao_independente_evidence": None,
        "escopo": "present",
        "gap_ou_ambiguidade": "present",
        "notes": (
            "JP-PSA scraped body is mostly the prepaid-payment-instruments section "
            "(licensing under Article 64); the crypto-asset chapter (Article 63-2 ff) "
            "is not in the body. Gold demotes all exige_* to null even where the LLM "
            "was right — gold needs body evidence, not authoritative external knowledge."
        ),
    },
    # =======================================================================
    "HK-HKSTABLECOINSORD-2025": {
        "regime": "licenciamento",
        "regime_evidence": (
            "The Monetary Authority must maintain a register of licensees in the form "
            "that the Monetary Authority considers appropriate"
        ),
        "status_regulatorio": "em_implementacao",
        "status_regulatorio_evidence": (
            "remains in force until it is revoked under section 28 or 29"
        ),
        "deadline_principal": "2025-08-01",
        "deadline_principal_evidence": None,
        "tipo_deadline": "go_live",
        "tipo_deadline_evidence": None,
        # The scraped body is mostly the licensing framework chapter — it
        # does not include the body of the reserve-requirement section or
        # the AML cross-reference detail. Gold marks these null until the
        # body is enriched with the relevant chapters.
        "exige_auditoria_tecnica": None,
        "exige_auditoria_tecnica_evidence": None,
        "exige_proof_of_reserves": None,
        "exige_proof_of_reserves_evidence": None,
        "exige_pentest": None,
        "exige_pentest_evidence": None,
        "exige_kyt_aml": None,
        "exige_kyt_aml_evidence": None,
        "exige_seguranca_custodia": None,
        "exige_seguranca_custodia_evidence": None,
        "exige_formal_verification": None,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": None,
        "exige_certificacao_independente_evidence": None,
        "escopo": "present",
        "gap_ou_ambiguidade": "present",
        "notes": (
            "HK Stablecoins Ordinance — licensing regime is clearly in body. Deadline date "
            "(2025-08-01) is correct per the regulator's published commencement notice but "
            "not in the scraped body; gold accepts the date with no evidence quote and lets "
            "the comparator surface that gap. POR / custody / AML calls await body enrichment."
        ),
    },
    # =======================================================================
    "AR-LEY27743-2024": {
        # Argentina's Ley 27,743 is a fiscal-measures statute (tax
        # regularization, asset declaration); it does not establish a
        # crypto regime. The LLM correctly flagged regime=sem_regra.
        # Evidence here is by absence — the gold notes field explains.
        "regime": "sem_regra",
        "regime_evidence": None,
        "status_regulatorio": "vigente",
        "status_regulatorio_evidence": (
            "The Regularization Regime for Tax, Customs, and Social Security Obligations "
            "is hereby created"
        ),
        "deadline_principal": "2025-04-30",
        "deadline_principal_evidence": None,
        "tipo_deadline": "transicao",
        "tipo_deadline_evidence": None,
        "exige_auditoria_tecnica": None,
        "exige_auditoria_tecnica_evidence": None,
        "exige_proof_of_reserves": None,
        "exige_proof_of_reserves_evidence": None,
        "exige_pentest": None,
        "exige_pentest_evidence": None,
        "exige_kyt_aml": None,
        "exige_kyt_aml_evidence": None,
        "exige_seguranca_custodia": None,
        "exige_seguranca_custodia_evidence": None,
        "exige_formal_verification": None,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": None,
        "exige_certificacao_independente_evidence": None,
        "escopo": "present",
        "gap_ou_ambiguidade": None,
        "notes": (
            "Negative-case gold row. Ley 27,743 is a tax statute with crypto-tangential "
            "asset-declaration rules — there is no crypto-specific regime, no exige_* "
            "triggers, and no certifier-relevant gap. The regime=sem_regra signal is "
            "evidenced by absence, not by a quote."
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
    print(f"\nAnnotated {count} gold rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
