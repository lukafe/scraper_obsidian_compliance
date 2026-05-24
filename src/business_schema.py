"""Business-layer schema for the crypto-lawmap vault.

The base vault stores 1+ legal norms per country (statute/regulation/guidance/
case_law). This module adds the *business* dimension on top — fields that
drive the commercial-opportunity scoring algorithm (CertiK use case).

Two complementary additions:

1. Norm-level fields (added to every existing note's frontmatter):
   regime, status_regulatorio, deadline_principal, exige_*, gatilho_servico,
   gap_ou_ambiguidade, confianca_dados, fontes, ultima_revisao.

2. Jurisdiction overviews (one per country, under `vault/_business/jur/{CC}.md`):
   aggregated view of the country's regulatory state, deadlines, services
   triggered, competitors, relationship strength.

Reguladores, serviços and competidores are STRINGS in frontmatter (not
separate nodes) in v1 — they can be promoted to nodes later if needed.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

# ---------- Controlled vocabularies ---------------------------------------

REGIONS = {
    "BR": "LATAM", "AR": "LATAM", "MX": "LATAM", "UY": "LATAM",
    "US": "NA", "CA": "NA", "BM": "NA",
    "EU": "EU", "DE": "EU", "FR": "EU", "IT": "EU", "LT": "EU",
    "GB": "EU",  # UK regulatorily adjacent
    "CH": "EU",  # non-EU but European
    "SG": "APAC", "JP": "APAC", "HK": "APAC", "KR": "APAC",
    "IN": "APAC", "ID": "APAC", "AU": "APAC", "NZ": "APAC",
    "AE": "MENA", "TR": "MENA",  # TR straddles
    "ZA": "Africa", "NG": "Africa",
    "INTL": "Supranational",
    "SE": "EU",
}

REGIME_VALUES = {
    "licenciamento", "registro", "proibicao", "sem_regra",
    "em_consulta", "desconhecido",
}

STATUS_REG_VALUES = {
    "vigente", "em_implementacao", "em_consulta", "proposto",
    "inexistente", "desconhecido",
}

MATURIDADE_VALUES = {"alta", "media", "baixa", "desconhecido"}

CONFIANCA_VALUES = {"alta", "media", "baixa"}

# CertiK security & compliance services — security-focused list.
# Anchored on the CertiK slide ("Elevating the Enterprise Web3 Journey") but
# expanded to capture any security-assessment service a regulator may demand.
SERVICOS_CERTIK = {
    # Security Auditing (slide)
    "smart_contract_audit",
    "l1_chain_audit",
    "penetration_testing",
    # Security & Compliance Products (slide)
    "skyinsights_aml_kyt",          # AML/KYT monitoring (SkyInsights)
    "skynet_threat_monitoring",     # on-chain risk monitoring (Skynet)
    "proof_of_reserves",
    "skyshield_bug_bounty",         # bug-bounty operation
    "performance_testing",
    "due_diligence",
    # Adjacent / cross-cutting security services not on the slide but
    # demanded by some regulations
    "formal_verification",
    "incident_response",
    "independent_certification",    # third-party certification as licensing
                                    # precondition (Brazilian IN BCB 701 case)
    # Advisory (slide) — security-relevant subset
    "security_guidance",            # advisory on security posture
    "regulatory_compliance_support",# certification roadmap for licensing
}


# Display labels (for the dashboard).
SERVICOS_CERTIK_LABELS = {
    "smart_contract_audit": "Smart Contract Audit",
    "l1_chain_audit": "L1 Chain Audit",
    "penetration_testing": "Penetration Testing",
    "skyinsights_aml_kyt": "SkyInsights — AML / KYT",
    "skynet_threat_monitoring": "Skynet — Threat Monitoring",
    "proof_of_reserves": "Proof of Reserves",
    "skyshield_bug_bounty": "Skyshield — Bug Bounty",
    "performance_testing": "Performance Testing",
    "due_diligence": "Due Diligence",
    "formal_verification": "Formal Verification",
    "incident_response": "Incident Response",
    "independent_certification": "Independent Certification",
    "security_guidance": "Security Guidance",
    "regulatory_compliance_support": "Regulatory Compliance Support",
}


# Category groupings (matches the slide's 3 columns).
SERVICE_CATEGORIES = {
    "Security Auditing": [
        "smart_contract_audit", "l1_chain_audit", "penetration_testing",
        "formal_verification",
    ],
    "Compliance & Monitoring Products": [
        "skyinsights_aml_kyt", "skynet_threat_monitoring",
        "proof_of_reserves", "skyshield_bug_bounty",
        "performance_testing", "due_diligence", "incident_response",
    ],
    "Advisory & Certification": [
        "independent_certification", "security_guidance",
        "regulatory_compliance_support",
    ],
}


# Boolean triggers (frontmatter exige_*) -> services they fire.
# Many triggers fire multiple services because a single regulatory
# requirement can be satisfied by, or motivate, several offerings.
SERVICE_TRIGGERS = {
    "exige_auditoria_tecnica": [
        "smart_contract_audit", "l1_chain_audit",
    ],
    "exige_proof_of_reserves": [
        "proof_of_reserves",
    ],
    "exige_pentest": [
        "penetration_testing",
    ],
    "exige_kyt_aml": [
        "skyinsights_aml_kyt",
    ],
    "exige_seguranca_custodia": [
        "penetration_testing", "skynet_threat_monitoring",
        "incident_response", "security_guidance",
    ],
    "exige_formal_verification": [
        "formal_verification",
    ],
    "exige_certificacao_independente": [
        "independent_certification", "due_diligence",
        "regulatory_compliance_support",
    ],
}


# Soft-text triggers — keywords found in `escopo` / `gap_ou_ambiguidade`
# that imply a service even when no boolean was extracted. Used by the
# enrichment re-derivation (no extra LLM call).
KEYWORD_TRIGGERS = {
    # English + Portuguese / Spanish / French / German keywords.
    "smart_contract_audit": [
        "smart contract", "smart-contract", "contract audit",
        "auditoria de contrato",
    ],
    "skynet_threat_monitoring": [
        "monitoring", "monitor", "on-chain analytics", "threat",
        "monitoramento", "vigilancia",
    ],
    "skyshield_bug_bounty": [
        "bug bounty", "vulnerability disclosure", "responsible disclosure",
    ],
    "incident_response": [
        "incident response", "breach notification", "data breach",
        "resposta a incidente",
    ],
    "due_diligence": [
        "due diligence", "vetting", "background check", "diligence",
    ],
    "skyinsights_aml_kyt": [
        "travel rule", "kyc", "kyt", "aml", "cft", "anti-money laundering",
        "suspicious transaction", "lavagem de dinheiro", "branqueamento",
    ],
    "proof_of_reserves": [
        "reserve", "proof of reserves", "attestation of reserves",
        "100% reserve", "reservas",
    ],
    "penetration_testing": [
        "penetration test", "pentest", "red team", "security testing",
    ],
    "performance_testing": [
        "performance test", "load test", "stress test",
    ],
    "regulatory_compliance_support": [
        "licensing", "authorization", "registration", "autorização",
        "licença", "registro",
    ],
}

TIPO_DEADLINE_VALUES = {
    "licenciamento", "transicao", "sunset", "consulta_publica",
    "go_live", "reporte_periodico", "desconhecido",
}

# ---------- Norm-level enrichment baseline --------------------------------

NORM_BUSINESS_FIELDS = {
    # Regime/status (mostly inferred from LLM analysis)
    "regime": None,
    "status_regulatorio": None,
    "deadline_principal": None,
    "tipo_deadline": None,
    # Service triggers (boolean — null = unknown)
    "exige_auditoria_tecnica": None,
    "exige_proof_of_reserves": None,
    "exige_pentest": None,
    "exige_kyt_aml": None,
    "exige_seguranca_custodia": None,
    "exige_formal_verification": None,
    "exige_certificacao_independente": None,
    # Derived from triggers
    "servicos_certik_aplicaveis": [],
    "gatilho_servico_certik": [],
    # Free-form (LLM-extracted)
    "gap_ou_ambiguidade": None,
    "escopo": None,  # plain-language summary of what the norm covers
    # Provenance
    "confianca_dados": "media",  # default for auto-enriched
    "fontes": [],
    "ultima_revisao": None,  # set on write
}


def baseline_business_fields() -> dict[str, Any]:
    """Return a fresh copy of the baseline business fields."""
    return {
        k: (list(v) if isinstance(v, list) else v)
        for k, v in NORM_BUSINESS_FIELDS.items()
    }


def derive_services_from_triggers(fm: dict[str, Any]) -> list[str]:
    """Materialize `servicos_certik_aplicaveis` from the `exige_*` flags
    PLUS keyword scans on `escopo` / `gap_ou_ambiguidade` fields.

    Returns a sorted unique list of service short labels.
    """
    out: set[str] = set()
    # 1) Boolean triggers
    for trigger_key, services in SERVICE_TRIGGERS.items():
        if fm.get(trigger_key) is True:
            for s in services:
                out.add(s)
    # 2) Keyword scans on extracted text
    text = (
        (fm.get("escopo") or "")
        + " "
        + (fm.get("gap_ou_ambiguidade") or "")
    ).lower()
    if text.strip():
        for service, kws in KEYWORD_TRIGGERS.items():
            for kw in kws:
                if kw in text:
                    out.add(service)
                    break
    return sorted(out)


# ---------- Jurisdiction overview schema ----------------------------------

# Fields for the per-country overview note (one note per CC).
JURISDICTION_OVERVIEW_FIELDS = (
    "tipo",                       # always "jurisdicao"
    "pais",                       # English name
    "iso",                        # ISO alpha-2
    "regiao",                     # LATAM/NA/EU/APAC/MENA/Africa
    "regulador_principal",        # string (e.g. "BCB")
    "reguladores_secundarios",    # list[str]
    "regime",                     # vocab
    "status_regulatorio",         # vocab
    "maturidade_mercado",         # vocab
    "deadline_principal",         # ISO date
    "tipo_deadline",              # vocab
    "frameworks_aplicaveis",      # list of wikilink strings
    "exige_auditoria_tecnica",    # boolean (aggregated: any norm exige)
    "exige_proof_of_reserves",
    "exige_pentest",
    "exige_kyt_aml",
    "exige_seguranca_custodia",
    "exige_formal_verification",
    "exige_certificacao_independente",
    "servicos_certik_aplicaveis", # list[str]
    "competidores_ativos",        # list[str]
    "forca_relacionamento_certik",# alta/media/baixa/nenhuma
    "oportunidade_score",         # null — algorithm fills later
    "confianca_dados",            # alta/media/baixa
    "fontes",                     # list[str]
    "ultima_revisao",             # ISO date
    "n_normas_total",             # int — count of underlying norms
    "n_normas_analyzed",          # int — how many had body analyzed
    "n_quarantine",               # int — count of quarantined notes
)


# ---------- Country name table (English, for overview display) -----------

COUNTRY_NAMES = {
    "BR": "Brazil", "TR": "Türkiye", "DE": "Germany", "FR": "France",
    "SG": "Singapore", "GB": "United Kingdom", "AE": "United Arab Emirates",
    "US": "United States", "HK": "Hong Kong", "CH": "Switzerland",
    "JP": "Japan", "KR": "South Korea", "LT": "Lithuania", "IT": "Italy",
    "MX": "Mexico", "AR": "Argentina", "NG": "Nigeria", "ZA": "South Africa",
    "UY": "Uruguay", "CA": "Canada", "BM": "Bermuda",
    "EU": "European Union", "IN": "India", "ID": "Indonesia",
    "AU": "Australia", "NZ": "New Zealand", "SE": "Sweden",
    "INTL": "Supranational standard-setters",
}


def today_iso() -> str:
    return date.today().isoformat()
