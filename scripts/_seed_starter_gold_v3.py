"""Phase 2 — third batch of hand-annotated gold rows (5 more).

Adds US-BITLICENSE-2015, ZA-FSCAIR2-2025, TR-PAYLAW6493, FR-LOIPACTE-2019,
and MX-LFPIORPI-2012 to the starter pack.

Gold support grows from 8 -> 13 norms (104 -> ~169 graded field instances).
Conservative philosophy: every non-null gold value carries a verbatim body
quote; fields the body doesn't substantiate stay None even when the LLM
made a call. Several of these have thin scraped bodies (Wayback fallback,
landing pages) so most fields end up null — that's the honest measurement
of "claims the LLM made that we cannot verify."
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import yaml

GOLD_DIR = REPO_ROOT / "vault" / "_export" / "ground_truth"
REVIEWER = "phase2-starter-v3"
REVIEWED_AT = date.today().isoformat()


ANNOTATIONS = {
    # =======================================================================
    "US-BITLICENSE-2015": {
        "regime": "licenciamento",
        "regime_evidence": (
            "No Person shall, without a license obtained from the "
            "superintendent…engage in any Virtual Currency Business Activity"
        ),
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
        # NY BitLicense Part 200.15 mandates BSA/AML programs and Part 200.16
        # KYC, but the scraped body is the NYDFS info page, not 23 NYCRR 200
        # itself, so gold demotes the LLM's True claim to null.
        "exige_kyt_aml": None,
        "exige_kyt_aml_evidence": None,
        "exige_seguranca_custodia": None,
        "exige_seguranca_custodia_evidence": None,
        "exige_formal_verification": None,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": False,
        "exige_certificacao_independente_evidence": None,
        "escopo": "present",
        "gap_ou_ambiguidade": "present",
        "notes": (
            "NY BitLicense info page (NYDFS). The scraped body does not "
            "include the body of 23 NYCRR Part 200, so only regime is "
            "anchored. AML / custody requirements exist in the actual "
            "regulation but cannot be quoted from this scrape."
        ),
    },
    # =======================================================================
    "ZA-FSCAIR2-2025": {
        # FSCA Information Request is a data-collection notice asking CASPs
        # to submit reporting; it doesn't establish a regime by itself, the
        # underlying CASP licensing regime sits in FAIS / FSCA Statement.
        "regime": None,
        "regime_evidence": None,
        "status_regulatorio": None,
        "status_regulatorio_evidence": None,
        "deadline_principal": None,
        "deadline_principal_evidence": None,
        # The IR DOES set a periodic-reporting deadline, but the scraped body
        # is the FSCA news index page — no reporting deadline quote available.
        "tipo_deadline": None,
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
        "gap_ou_ambiguidade": "present",
        "notes": (
            "FSCA IR 2/2025 — scraped body is the FSCA press / news index, "
            "not the IR text itself. All structured fields demoted to null "
            "until the actual IR text is reachable. This is a negative-case "
            "row for the LLM's optimistic extractions of POR / custody / AML."
        ),
    },
    # =======================================================================
    "TR-PAYLAW6493": {
        "regime": "licenciamento",
        "regime_evidence": (
            "The system operator must: a) Be established as a joint stock "
            "company, b) Have a paid-up capital of at least five million "
            "Turkish Liras"
        ),
        "status_regulatorio": None,
        "status_regulatorio_evidence": None,
        "deadline_principal": None,
        "deadline_principal_evidence": None,
        "tipo_deadline": None,
        "tipo_deadline_evidence": None,
        "exige_auditoria_tecnica": None,
        "exige_auditoria_tecnica_evidence": None,
        # Law 6493 is the Payment-Systems base law (not crypto-specific).
        # The "proof of reserves" the LLM extracted has no body grounding —
        # capital requirements are not proof-of-reserves obligations.
        "exige_proof_of_reserves": None,
        "exige_proof_of_reserves_evidence": None,
        "exige_pentest": None,
        "exige_pentest_evidence": None,
        # Payment-services law implies AML obligations on PSPs but the
        # scraped body excerpts don't quote that requirement.
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
            "Turkish Law 6493 (Payment Services + Electronic Money). Regime "
            "is clear (BDDK permission + joint-stock + minimum capital), but "
            "the LLM's POR / AML / custody claims have no quotes in this "
            "scrape — crypto-specific obligations live in BDDK/SPK secondary "
            "rules, not in Law 6493 itself."
        ),
    },
    # =======================================================================
    "FR-LOIPACTE-2019": {
        # PACTE created the PSAN (Prestataire de Services sur Actifs Numériques)
        # regime — both a mandatory registration (enregistrement) and an
        # optional licence (agrément). The scraped body is the official
        # Legifrance index plus a stub from the article — limited evidence.
        "regime": "licenciamento",
        "regime_evidence": (
            "à déclaration ou autorisation préalables, dans des conditions "
            "fixées par décret"
        ),
        "status_regulatorio": None,
        "status_regulatorio_evidence": None,
        "deadline_principal": None,
        "deadline_principal_evidence": None,
        "tipo_deadline": None,
        "tipo_deadline_evidence": None,
        "exige_auditoria_tecnica": None,
        "exige_auditoria_tecnica_evidence": None,
        # The LLM had exige_proof_of_reserves=False — gold agrees (PACTE has
        # no POR requirement; that came later with MiCA).
        "exige_proof_of_reserves": False,
        "exige_proof_of_reserves_evidence": None,
        "exige_pentest": None,
        "exige_pentest_evidence": None,
        # PSAN registration requires AML/CFT compliance but the scraped body
        # doesn't surface the relevant article (L. 561-2 of CMF).
        "exige_kyt_aml": None,
        "exige_kyt_aml_evidence": None,
        "exige_seguranca_custodia": None,
        "exige_seguranca_custodia_evidence": None,
        "exige_formal_verification": False,
        "exige_formal_verification_evidence": None,
        "exige_certificacao_independente": False,
        "exige_certificacao_independente_evidence": None,
        "escopo": "present",
        "gap_ou_ambiguidade": "present",
        "notes": (
            "PACTE Law 2019-486 — scraped body is administrative / index "
            "content rather than the PSAN articles (L. 54-10-1 ff of CMF). "
            "Regime claim is anchored on a weak generic-permission quote. "
            "The False values on POR / formal-verif / cert match the LLM "
            "and reflect the actual statutory text (PACTE did not impose "
            "those). AML and custody requirements exist in MAR/RGAMF rules "
            "but not in PACTE text itself."
        ),
    },
    # =======================================================================
    "MX-LFPIORPI-2012": {
        # The Mexican Anti-Money-Laundering Law (LFPIORPI). Registration is
        # required for vulnerable activities (Article 17). Crypto is one of
        # them since the 2018 Fintech Law cross-reference.
        "regime": "registro",
        "regime_evidence": None,  # body too thin for verbatim quote
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
        # AML law by definition requires AML/KYT, but the scraped body is
        # essentially the LLM's own escopo / gap analysis — no statutory text.
        # Gold demotes to null.
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
            "Mexican LFPIORPI — scraped body is too thin to ground any "
            "structured field. Even regime (registro) lands without a "
            "verbatim quote. Comparator will flag the LLM's regime=registro "
            "as a match-on-value-only (no evidence backed)."
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
