// Translation maps from the raw vocabulary stored in the vault (Portuguese)
// to the canonical English labels surfaced in the UI. The data files in
// public/data/*.json still carry the original tokens — translate at render
// time so the underlying corpus remains a faithful mirror of the pipeline.

const REGIME: Record<string, string> = {
  licenciamento: "Licensing",
  registro: "Registration",
  proibicao: "Prohibition",
  em_consulta: "Under consultation",
  sem_regra: "Silent",
  notificacao: "Notification",
  autorregulacao: "Self-regulation",
  desconhecido: "Unknown",
};

const STATUS_REGULATORIO: Record<string, string> = {
  vigente: "In force",
  em_implementacao: "Implementing",
  em_consulta: "Under consultation",
  proposto: "Proposed",
  revogado: "Repealed",
  suspenso: "Suspended",
  desconhecido: "Unknown",
};

const MATURITY: Record<string, string> = {
  alta: "High",
  media: "Medium",
  baixa: "Low",
  desconhecido: "Unknown",
};

const CONFIDENCE: Record<string, string> = {
  alta: "High",
  media: "Medium",
  baixa: "Low",
};

const TIPO_DEADLINE: Record<string, string> = {
  vigencia: "Effective date",
  conformidade: "Compliance deadline",
  fim_periodo_transitorio: "End of transition period",
  consulta_publica: "Public consultation closes",
  registro: "Registration deadline",
};

const EDGE_TYPE: Record<string, string> = {
  derivado_de: "Derived from",
  inspirado_em: "Inspired by",
  referencia_cruzada: "Cross-reference",
  regulado_por: "Regulated by",
  exige_servico: "Triggers service",
  precede_deadline: "Precedes deadline",
  aplica_se_a: "Applies to",
  citation: "Citation",
  semantic: "Semantic link",
};

function pick(map: Record<string, string>, value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return map[value] ?? toTitle(value);
}

function toTitle(s: string): string {
  return s
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export const label = {
  regime: (v: string | null | undefined) => pick(REGIME, v),
  status: (v: string | null | undefined) => pick(STATUS_REGULATORIO, v),
  maturity: (v: string | null | undefined) => pick(MATURITY, v),
  confidence: (v: string | null | undefined) => pick(CONFIDENCE, v),
  deadlineType: (v: string | null | undefined) => pick(TIPO_DEADLINE, v),
  edgeType: (v: string | null | undefined) => pick(EDGE_TYPE, v),
};

// Maturity rank for the scoring layer — keyed by the *raw* vocabulary so the
// data file does not need to be rewritten.
export const MATURITY_RANK: Record<string, number> = {
  alta: 3,
  media: 2,
  baixa: 1,
  desconhecido: 0,
};
