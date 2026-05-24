// Types mirroring web/public/data/*.json

export interface Jurisdiction {
  iso: string;
  pais: string;
  regiao: string;
  regulador_principal: string | null;
  reguladores_secundarios: string[];
  regime: string | null;
  status_regulatorio: string | null;
  maturidade_mercado: "alta" | "media" | "baixa" | "desconhecido" | null;
  deadline_principal: string | null;
  tipo_deadline: string | null;
  urgencia_deadline_dias: number | null;
  exige_auditoria_tecnica: boolean | null;
  exige_proof_of_reserves: boolean | null;
  exige_pentest: boolean | null;
  exige_kyt_aml: boolean | null;
  exige_seguranca_custodia: boolean | null;
  exige_formal_verification: boolean | null;
  exige_certificacao_independente: boolean | null;
  servicos: string[];
  n_servicos: number;
  /** Phase 4 — set of regulatory dimensions actually addressed by this
   *  jurisdiction's underlying norms (derived from text, not from a
   *  structural heuristic). See `src/coverage.py`. */
  cobertura_regulatoria: string[];
  n_cobertura: number;
  n_normas_total: number;
  n_normas_analyzed: number;
  n_quarantine: number;
  frameworks: string[];
  inlinks_grafo: number;
  outlinks_grafo: number;
  confianca_dados: string | null;
  ultima_revisao: string | null;
}

export const COVERAGE_DIMENSION_LABELS: Record<string, string> = {
  issuance: "Token issuance",
  custody: "Custody",
  market_abuse: "Market abuse",
  aml: "AML / KYT",
  taxation: "Taxation",
  consumer_protection: "Consumer protection",
};

export const COVERAGE_DIMENSIONS = [
  "issuance",
  "custody",
  "market_abuse",
  "aml",
  "taxation",
  "consumer_protection",
] as const;

export interface Norm {
  id: string;
  country: string;
  jurisdiction: string;
  type: string;
  title: string;
  title_original: string | null;
  regulator: string | null;
  date: string | null;
  status: string;
  discovered_via: string;
  source_url: string | null;
  source_authority: string | null;
  confidence: number | null;
  regime: string | null;
  status_regulatorio: string | null;
  deadline_principal: string | null;
  tipo_deadline: string | null;
  urgencia_deadline_dias: number | null;
  exige_auditoria_tecnica: boolean | null;
  exige_proof_of_reserves: boolean | null;
  exige_pentest: boolean | null;
  exige_kyt_aml: boolean | null;
  exige_seguranca_custodia: boolean | null;
  exige_formal_verification: boolean | null;
  exige_certificacao_independente: boolean | null;
  servicos: string[];
  n_servicos: number;
  escopo: string | null;
  gap_ou_ambiguidade: string | null;
  /** Verbatim quotes from the source body backing each structured field.
   *  Empty for fields the analyzer could not support with a quote. */
  evidence?: Partial<Record<EvidenceField, string>>;
  n_inlinks: number;
  n_outlinks: number;
  confianca_dados: string | null;
  in_quarantine: boolean;
}

export type EvidenceField =
  | "regime"
  | "status_regulatorio"
  | "deadline_principal"
  | "tipo_deadline"
  | "exige_auditoria_tecnica"
  | "exige_proof_of_reserves"
  | "exige_pentest"
  | "exige_kyt_aml"
  | "exige_seguranca_custodia"
  | "exige_formal_verification"
  | "exige_certificacao_independente";

export interface GraphNode {
  id: string;
  kind: "jurisdicao" | "lei";
  label: string;
  country?: string;
  regiao?: string;
  type?: string;
  regulator?: string;
  date?: string;
  source_authority?: string;
  confidence?: number;
  status?: string;
  regime?: string;
  status_regulatorio?: string;
  deadline_principal?: string;
  urgencia_deadline_dias?: number | null;
  servicos_certik_aplicaveis?: string[];
  n_inlinks?: number;
  in_quarantine?: boolean;
  confianca_dados?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  tipo_relacao: string;
  peso: number;
  justificativa?: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  generated?: string;
}

// Service catalog (mirror of business_schema.py).
export const SERVICE_LABELS: Record<string, string> = {
  smart_contract_audit: "Smart Contract Audit",
  l1_chain_audit: "L1 Chain Audit",
  penetration_testing: "Penetration Testing",
  skyinsights_aml_kyt: "SkyInsights — AML / KYT",
  skynet_threat_monitoring: "Skynet — Threat Monitoring",
  proof_of_reserves: "Proof of Reserves",
  skyshield_bug_bounty: "Skyshield — Bug Bounty",
  performance_testing: "Performance Testing",
  due_diligence: "Due Diligence",
  formal_verification: "Formal Verification",
  incident_response: "Incident Response",
  independent_certification: "Independent Certification",
  security_guidance: "Security Guidance",
  regulatory_compliance_support: "Regulatory Compliance Support",
};

export const SERVICE_CATEGORIES: Record<string, string[]> = {
  "Security Auditing": [
    "smart_contract_audit", "l1_chain_audit",
    "penetration_testing", "formal_verification",
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
};

export const ISO2_TO_ISO3: Record<string, string> = {
  BR: "BRA", AR: "ARG", MX: "MEX", UY: "URY",
  US: "USA", CA: "CAN", BM: "BMU",
  DE: "DEU", FR: "FRA", IT: "ITA", LT: "LTU", GB: "GBR",
  CH: "CHE",
  SG: "SGP", JP: "JPN", HK: "HKG", KR: "KOR",
  IN: "IND", AE: "ARE", TR: "TUR",
  ZA: "ZAF", NG: "NGA", SE: "SWE",
};

export const ISO3_TO_ISO2: Record<string, string> = Object.fromEntries(
  Object.entries(ISO2_TO_ISO3).map(([k, v]) => [v, k]),
);
