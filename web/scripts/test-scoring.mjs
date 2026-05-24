#!/usr/bin/env node
/**
 * Phase 4 — verify the opportunity-score reshape works as designed:
 *   - past-due decays from 100 toward 50 over 12 months (no perpetual saturation)
 *   - null deadline + known regime => urgency = 30
 *   - null deadline + unknown regime => urgency = 0
 *   - future deadlines unchanged (730-day curve)
 *
 * Re-implements the formula inline (no TS compilation step) and asserts
 * against a handful of representative jurisdictions.
 */

const MATURITY_RANK = { alta: 3, media: 2, baixa: 1, desconhecido: 0 };
const PAST_DUE_FLOOR = 50;
const PAST_DUE_HALF_LIFE_DAYS = 365;
const NO_DEADLINE_KNOWN_REGIME = 30;
const NO_DEADLINE_UNKNOWN_REGIME = 0;
const FUTURE_HORIZON_DAYS = 730;

function urgencyComponent(j) {
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

function opportunityScore(j) {
  const urgency = urgencyComponent(j);
  const intensity = (j.n_servicos / 14) * 100;
  const maturity = ((MATURITY_RANK[j.maturidade_mercado ?? "desconhecido"] ?? 0) / 3) * 100;
  return Math.round((0.4 * urgency + 0.4 * intensity + 0.2 * maturity) * 10) / 10;
}

let passed = 0;
let failed = 0;
function check(name, got, want, tol = 0.05) {
  const ok = Math.abs(got - want) <= tol;
  console.log(`  ${ok ? "PASS" : "FAIL"} ${name}  got=${got} want~${want}`);
  if (ok) passed += 1; else failed += 1;
}

console.log("[urgency component]");
check("future 0 days -> 100", urgencyComponent({ urgencia_deadline_dias: 0 }), 100);
check("future 365 days -> 50", urgencyComponent({ urgencia_deadline_dias: 365 }), 50);
check("future 730 days -> 0", urgencyComponent({ urgencia_deadline_dias: 730 }), 0);
check(
  "past 1 day -> ~99.86",
  urgencyComponent({ urgencia_deadline_dias: -1 }),
  100 - (1 / 365) * 50,
);
check(
  "past 6 months -> ~75 (halfway through decay)",
  urgencyComponent({ urgencia_deadline_dias: -180 }),
  100 - (180 / 365) * 50,
);
check(
  "past 12 months -> 50 (floor)",
  urgencyComponent({ urgencia_deadline_dias: -365 }),
  PAST_DUE_FLOOR,
);
check(
  "past 24 months -> 50 (clamped at floor)",
  urgencyComponent({ urgencia_deadline_dias: -730 }),
  PAST_DUE_FLOOR,
);
check(
  "null + known regime -> 30",
  urgencyComponent({ urgencia_deadline_dias: null, regime: "licenciamento" }),
  30,
);
check(
  "null + unknown regime -> 0",
  urgencyComponent({ urgencia_deadline_dias: null, regime: null }),
  0,
);

console.log("\n[full score combinations]");
check(
  "Hot market (future 30d, 10/14 services, alta)",
  opportunityScore({
    urgencia_deadline_dias: 30,
    n_servicos: 10,
    maturidade_mercado: "alta",
    regime: "licenciamento",
  }),
  0.4 * (100 - (30 / 730) * 100) + 0.4 * (10 / 14) * 100 + 0.2 * 100,
);
check(
  "Cool market (null deadline, unknown regime, 0 services)",
  opportunityScore({
    urgencia_deadline_dias: null,
    n_servicos: 0,
    maturidade_mercado: "desconhecido",
    regime: null,
  }),
  0,
);
check(
  "Quiet but established market (null deadline, known regime, 6/14 services, media)",
  opportunityScore({
    urgencia_deadline_dias: null,
    n_servicos: 6,
    maturidade_mercado: "media",
    regime: "licenciamento",
  }),
  0.4 * 30 + 0.4 * (6 / 14) * 100 + 0.2 * (2 / 3) * 100,
);

console.log();
if (failed === 0) {
  console.log(`All ${passed} scoring assertions passed.`);
  process.exit(0);
} else {
  console.log(`${failed} of ${passed + failed} scoring assertions FAILED.`);
  process.exit(1);
}
