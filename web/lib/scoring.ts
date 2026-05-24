import { Jurisdiction } from "./types";
import { MATURITY_RANK } from "./labels";

/**
 * Composite opportunity score (0-100).
 *   40% urgency  - days to the next regulatory deadline
 *   40% service intensity - share of CertiK services triggered
 *   20% market maturity - heuristic (regulators x analyzed norms x age)
 *
 * Past-due deadlines saturate at 100 on the urgency axis; missing deadlines
 * receive a neutral 20 to avoid masking otherwise strong markets.
 */
export function opportunityScore(j: Jurisdiction): number {
  const days = j.urgencia_deadline_dias;
  let urgency: number;
  if (days === null) urgency = 20;
  else if (days < 0) urgency = 100;
  else urgency = Math.max(0, 100 - (days / 730) * 100);

  const intensity = (j.n_servicos / 14) * 100;
  const maturity = ((MATURITY_RANK[j.maturidade_mercado ?? "desconhecido"] ?? 0) / 3) * 100;
  return Math.round((0.4 * urgency + 0.4 * intensity + 0.2 * maturity) * 10) / 10;
}

export function rankJurisdictions(juris: Jurisdiction[]): (Jurisdiction & { score: number })[] {
  return juris
    .map((j) => ({ ...j, score: opportunityScore(j) }))
    .sort((a, b) => b.score - a.score);
}

export function urgencyBucket(
  days: number | null,
): "past" | "<= 90 days" | "<= 1 year" | "> 1 year" | "no deadline" {
  if (days === null) return "no deadline";
  if (days < 0) return "past";
  if (days <= 90) return "<= 90 days";
  if (days <= 365) return "<= 1 year";
  return "> 1 year";
}

export function urgencyColor(days: number | null): string {
  if (days === null) return "#555";
  if (days < 0) return "#888";
  if (days <= 90) return "#F44336";
  if (days <= 365) return "#FFB300";
  return "#4CAF50";
}

export function maturityColor(m: string | null): string {
  if (m === "alta") return "#4CAF50";
  if (m === "media") return "#FFB300";
  if (m === "baixa") return "#F44336";
  return "#666";
}
