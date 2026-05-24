#!/usr/bin/env node
/**
 * Reads vault/_export/{jurisdicoes.csv, normas.csv, grafo.json}
 * and writes typed JSON to web/public/data/ for the Next.js app.
 *
 * Runs as `predev` and `prebuild` so the dashboard always reflects the
 * latest vault export. If the export files don't exist (e.g. on Vercel
 * build where the vault isn't checked in), it tries the pre-committed
 * `web/public/data/*` (no-op fallback).
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "csv-parse/sync";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const repoRoot = path.resolve(webRoot, "..");
const exportDir = path.join(repoRoot, "vault", "_export");
const outDir = path.join(webRoot, "public", "data");

fs.mkdirSync(outDir, { recursive: true });

const log = (...a) => console.log("[prepare-data]", ...a);

/* ---------- helpers ---------- */

function parseCsv(filename) {
  const p = path.join(exportDir, filename);
  if (!fs.existsSync(p)) {
    log(`SKIP (missing): ${p}`);
    return null;
  }
  const raw = fs.readFileSync(p, "utf-8");
  return parse(raw, { columns: true, skip_empty_lines: true });
}

function copyJson(filename) {
  const src = path.join(exportDir, filename);
  if (!fs.existsSync(src)) {
    log(`SKIP (missing): ${src}`);
    return;
  }
  const dst = path.join(outDir, filename);
  fs.copyFileSync(src, dst);
  log(`copied ${filename} -> public/data/${filename}`);
}

function num(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function bool(v) {
  if (v === "True" || v === "true") return true;
  if (v === "False" || v === "false") return false;
  return null;
}

function listFromPipe(v) {
  if (!v) return [];
  return String(v).split("|").map((s) => s.trim()).filter(Boolean);
}

/* ---------- jurisdictions ---------- */

const jurRows = parseCsv("jurisdicoes.csv");
if (jurRows) {
  const jurisdictions = jurRows.map((r) => ({
    iso: r.iso,
    pais: r.pais,
    regiao: r.regiao,
    regulador_principal: r.regulador_principal || null,
    reguladores_secundarios: listFromPipe(r.reguladores_secundarios_csv),
    regime: r.regime || null,
    status_regulatorio: r.status_regulatorio || null,
    maturidade_mercado: r.maturidade_mercado || null,
    deadline_principal: r.deadline_principal || null,
    tipo_deadline: r.tipo_deadline || null,
    urgencia_deadline_dias: num(r.urgencia_deadline_dias),
    exige_auditoria_tecnica: bool(r.exige_auditoria_tecnica),
    exige_proof_of_reserves: bool(r.exige_proof_of_reserves),
    exige_pentest: bool(r.exige_pentest),
    exige_kyt_aml: bool(r.exige_kyt_aml),
    exige_seguranca_custodia: bool(r.exige_seguranca_custodia),
    exige_formal_verification: bool(r.exige_formal_verification),
    exige_certificacao_independente: bool(r.exige_certificacao_independente),
    servicos: listFromPipe(r.servicos_certik_aplicaveis_csv),
    n_servicos: num(r.n_servicos) ?? 0,
    cobertura_regulatoria: listFromPipe(r.cobertura_regulatoria_csv),
    n_cobertura: num(r.n_cobertura) ?? 0,
    n_normas_total: num(r.n_normas_total) ?? 0,
    n_normas_analyzed: num(r.n_normas_analyzed) ?? 0,
    n_quarantine: num(r.n_quarantine) ?? 0,
    frameworks: listFromPipe(r.frameworks_aplicaveis_csv),
    inlinks_grafo: num(r.inlinks_grafo) ?? 0,
    outlinks_grafo: num(r.outlinks_grafo) ?? 0,
    confianca_dados: r.confianca_dados || null,
    ultima_revisao: r.ultima_revisao || null,
  }));
  fs.writeFileSync(
    path.join(outDir, "jurisdicoes.json"),
    JSON.stringify(jurisdictions, null, 0),
  );
  log(`wrote jurisdicoes.json (${jurisdictions.length} rows)`);
}

/* ---------- norms ---------- */

const EVIDENCE_FIELDS = [
  "regime",
  "status_regulatorio",
  "deadline_principal",
  "tipo_deadline",
  "exige_auditoria_tecnica",
  "exige_proof_of_reserves",
  "exige_pentest",
  "exige_kyt_aml",
  "exige_seguranca_custodia",
  "exige_formal_verification",
  "exige_certificacao_independente",
];

const normRows = parseCsv("normas.csv");
if (normRows) {
  const norms = normRows.map((r) => {
    const evidence = {};
    for (const f of EVIDENCE_FIELDS) {
      const v = r[`${f}_evidence`];
      if (v) evidence[f] = v;
    }
    return {
      id: r.id,
      country: r.country,
      jurisdiction: r.jurisdiction,
      type: r.type,
      title: r.title,
      title_original: r.title_original || null,
      regulator: r.regulator || null,
      date: r.date || null,
      status: r.status,
      discovered_via: r.discovered_via,
      source_url: r.source_url || null,
      source_authority: r.source_authority || null,
      confidence: num(r.confidence),
      regime: r.regime || null,
      status_regulatorio: r.status_regulatorio || null,
      deadline_principal: r.deadline_principal || null,
      tipo_deadline: r.tipo_deadline || null,
      urgencia_deadline_dias: num(r.urgencia_deadline_dias),
      exige_auditoria_tecnica: bool(r.exige_auditoria_tecnica),
      exige_proof_of_reserves: bool(r.exige_proof_of_reserves),
      exige_pentest: bool(r.exige_pentest),
      exige_kyt_aml: bool(r.exige_kyt_aml),
      exige_seguranca_custodia: bool(r.exige_seguranca_custodia),
      exige_formal_verification: bool(r.exige_formal_verification),
      exige_certificacao_independente: bool(r.exige_certificacao_independente),
      servicos: listFromPipe(r.servicos_certik_aplicaveis_csv),
      n_servicos: num(r.n_servicos) ?? 0,
      escopo: r.escopo || null,
      gap_ou_ambiguidade: r.gap_ou_ambiguidade || null,
      evidence,
      n_inlinks: num(r.n_inlinks) ?? 0,
      n_outlinks: num(r.n_outlinks) ?? 0,
      confianca_dados: r.confianca_dados || null,
      in_quarantine: r.in_quarantine === "True" || r.in_quarantine === "true",
    };
  });
  fs.writeFileSync(
    path.join(outDir, "normas.json"),
    JSON.stringify(norms, null, 0),
  );
  log(`wrote normas.json (${norms.length} rows)`);
}

/* ---------- graph ---------- */

copyJson("grafo.json");

/* ---------- metadata ---------- */

const meta = {
  built_at: new Date().toISOString(),
  vault_export_present: jurRows !== null,
};
fs.writeFileSync(
  path.join(outDir, "meta.json"),
  JSON.stringify(meta, null, 2),
);
log("done", meta);
