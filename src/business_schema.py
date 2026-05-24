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

# CertiK services (canonical short labels)
SERVICOS_CERTIK = {
    "audit_smart_contract",
    "proof_of_reserves",
    "kyt_aml",
    "pentest",
    "formal_verification",
    "certificacao_independente",
    "incident_response",
    "skynet_monitoring",
}

# Triggers — regulatory conditions that fire a CertiK service
SERVICE_TRIGGERS = {
    "exige_auditoria_tecnica": "audit_smart_contract",
    "exige_proof_of_reserves": "proof_of_reserves",
    "exige_pentest": "pentest",
    "exige_kyt_aml": "kyt_aml",
    "exige_seguranca_custodia": "pentest",  # related but not 1:1
    "exige_formal_verification": "formal_verification",
    "exige_certificacao_independente": "certificacao_independente",
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
    """Materialize `servicos_certik_aplicaveis` from the `exige_*` flags."""
    out: list[str] = []
    for trigger_key, service in SERVICE_TRIGGERS.items():
        if fm.get(trigger_key) is True and service not in out:
            out.append(service)
    return out


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
