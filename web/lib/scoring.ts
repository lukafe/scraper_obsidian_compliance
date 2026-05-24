import { Jurisdiction } from "./types";
import { MATURITY_RANK } from "./labels";

/**
 * Phase 4 — text-grounded opportunity score (0-100).
 *
 *   40% Urgency   - days to the next regulatory deadline, with three fixes:
 *                   (1) past-due decays from 100 toward a 50 floor over
 *                       12 months instead of saturating forever;
 *                   (2) null deadline + known regime = 30 (rule in force,
 *                       no calendar pressure — still a real market);
 *                   (3) null deadline + unknown regime = 0 (insufficient
 *                       signal — do not promote on no information).
 *
 *   40% Service intensity - share of CertiK services triggered.
 *
 *   20% Coverage-grounded maturity - now driven by the actual breadth of
 *        regulatory dimensions addressed (issuance, custody, market abuse,
 *        AML, taxation, consumer protection). The 40/3/2020 magic numbers
 *        are gone; see `src/coverage.py`.
 */
export function opportunityScore(j: Jurisdiction): number {
  const urgency = urgencyComponent(j);
  const intensity = (j.n_servicos / 14) * 100;
  const maturity = ((MATURITY_RANK[j.maturidade_mercado ?? "desconhecido"] ?? 0) / 3) * 100;
  return Math.round((0.4 * urgency + 0.4 * intensity + 0.2 * maturity) * 10) / 10;
}

const PAST_DUE_FLOOR = 50;
const PAST_DUE_HALF_LIFE_DAYS = 365;
const NO_DEADLINE_KNOWN_REGIME = 30;
const NO_DEADLINE_UNKNOWN_REGIME = 0;
const FUTURE_HORIZON_DAYS = 730;

function urgencyComponent(j: Jurisdiction): number {
  const days = j.urgencia_deadline_dias;
  if (days === null) {
    return j.regime ? NO_DEADLINE_KNOWN_REGIME : NO_DEADLINE_UNKNOWN_REGIME;
  }
  if (days < 0) {
    const monthsPast = Math.abs(days) / 30;
    const decay = (monthsPast * 30) / PAST_DUE_HALF_LIFE_DAYS;
    return Math.max(PAST_DUE_FLOOR, 100 - decay * (100 - PAST_DUE_FLOOR));
  }
  return Math.max(0, 100 - (days / FUTURE_HORIZON_DAYS) * 100);
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
