"""Phase 4 — text-grounded regulatory-coverage detection.

The legacy `maturidade_mercado` was a structural heuristic
(40 norms / 3 regulators / anchor < 2020). Phase 4 replaces it with a
*coverage* signal: which of the six core regulatory dimensions does this
jurisdiction's body of norms actually address?

Dimensions:
    issuance              - token issuance, whitepapers, public offerings
    custody               - custody of client assets, segregation, cold storage
    market_abuse          - market manipulation, insider trading, abuse
    aml                   - AML / CFT / Travel Rule
    taxation              - tax treatment of crypto assets
    consumer_protection   - disclosure, complaints, suitability, retail rules

Detection is conservative: for each norm we check (a) Phase 1 evidence
quotes if present, (b) the LLM-extracted `escopo` / `gap_ou_ambiguidade`
text, and (c) certain `exige_*` boolean triggers. Word-boundary matching
via `validators.keyword_hits` keeps the false-positive rate low.

The jurisdiction-level signal is OR over its norms — one well-supported
norm is enough to count the dimension as covered.

Maturity mapping (six dimensions, two thresholds):
    high   >= 5 covered     "comprehensive framework"
    medium >= 3 covered     "core framework in place"
    low    >= 1 covered     "fragmented coverage"
    unknown 0               "no signal extracted"
"""

from __future__ import annotations

from typing import Any, Iterable

from . import validators


COVERAGE_DIMENSIONS = (
    "issuance",
    "custody",
    "market_abuse",
    "aml",
    "taxation",
    "consumer_protection",
)


# Multilingual keyword vocabulary per dimension. Kept short and high-precision:
# every entry is a phrase or a >=4-char token that survives word-boundary
# matching. Generic single-word tokens (e.g. "tax") are kept where the loss
# of recall would be greater than the false-positive risk.
_COVERAGE_KEYWORDS: dict[str, list[str]] = {
    "issuance": [
        "issuance", "offering", "offerings", "white paper", "whitepaper",
        "whitepapers", "prospectus", "ico", "sto", "token sale",
        "token sales", "public offering",
        "emissao", "emissão", "oferta pública", "emisión",
        "emission", "wertpapierprospekt",
    ],
    "custody": [
        "custody", "custodian", "custodians", "safekeeping", "segregation",
        "cold storage", "wallet", "wallets", "private key", "private keys",
        "custodia", "custódia", "guarda de ativos",
        "verwahrung", "aufbewahrung", "garde",
    ],
    "market_abuse": [
        "market abuse", "market manipulation", "insider trading",
        "insider dealing", "front running", "wash trading",
        "abuso de mercado", "manipulação", "manipulacion",
        "marktmanipulation", "insiderhandel",
    ],
    "aml": [
        "aml", "cft", "kyc", "kyt", "travel rule",
        "anti-money laundering", "money laundering",
        "suspicious transaction", "sanctions",
        "lavagem de dinheiro", "branqueamento",
        "blanchiment", "geldwäsche",
    ],
    "taxation": [
        "taxation", "tax treatment", "income tax", "capital gains",
        "tax authority", "tax obligation", "taxes",
        "tributação", "imposto sobre", "tributario",
        "tributación", "fiscalité", "besteuerung", "steuer",
    ],
    "consumer_protection": [
        "consumer protection", "consumer protections",
        "retail investor", "retail investors", "retail client",
        "retail clients", "suitability", "disclosure", "disclosures",
        "complaints", "warning", "warnings",
        "proteção do consumidor", "protección al consumidor",
        "protection des consommateurs", "verbraucherschutz",
        "anlegerschutz",
    ],
}


# Boolean `exige_*` triggers that directly imply coverage of a dimension.
# Only the strongest implications are wired here — keyword scans cover the
# rest defensively.
_TRIGGER_TO_DIMENSION: dict[str, str] = {
    "exige_seguranca_custodia": "custody",
    "exige_kyt_aml": "aml",
}


def detect_norm_coverage(extra: dict[str, Any]) -> set[str]:
    """Return the set of dimensions covered by a single norm's extracted
    signals. Inputs are read non-destructively from the note's frontmatter.
    """
    covered: set[str] = set()

    # 1) Boolean triggers — strongest signal, no false-positive risk.
    for trigger, dim in _TRIGGER_TO_DIMENSION.items():
        if extra.get(trigger) is True:
            covered.add(dim)

    # 2) Phase-1 evidence quotes (if populated) — already grounded.
    text_parts: list[str] = []
    for f in (
        "escopo", "gap_ou_ambiguidade",
        "regime_evidence",
        "status_regulatorio_evidence",
        "exige_auditoria_tecnica_evidence",
        "exige_proof_of_reserves_evidence",
        "exige_pentest_evidence",
        "exige_kyt_aml_evidence",
        "exige_seguranca_custodia_evidence",
        "exige_formal_verification_evidence",
        "exige_certificacao_independente_evidence",
    ):
        v = extra.get(f)
        if isinstance(v, str) and v:
            text_parts.append(v)
    text = " ".join(text_parts)

    if text:
        for dim, kws in _COVERAGE_KEYWORDS.items():
            if dim in covered:
                continue
            if validators.keyword_hits(text, kws):
                covered.add(dim)

    return covered


def aggregate_coverage(norms_extras: Iterable[dict[str, Any]]) -> set[str]:
    """OR across norms — a single supported norm is enough to mark the
    jurisdiction as covering that dimension.
    """
    covered: set[str] = set()
    for extra in norms_extras:
        covered |= detect_norm_coverage(extra)
    return covered


def maturity_from_coverage(covered: set[str]) -> str:
    """Map a set of covered dimensions to a maturity label that is
    consistent with the legacy `MATURIDADE_VALUES` vocabulary.

    The thresholds are conservative — high requires near-complete coverage
    (5+ of 6 dimensions), reflecting that a "high-maturity" market should
    actually have a comprehensive framework, not just many fragmentary
    rules.
    """
    n = len(covered)
    if n >= 5:
        return "alta"
    if n >= 3:
        return "media"
    if n >= 1:
        return "baixa"
    return "desconhecido"
