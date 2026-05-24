// Server-side data loaders. Read JSON at request time (cached in production
// because `output: "standalone"` + static-ish pages).

import fs from "node:fs";
import path from "node:path";
import { Graph, Jurisdiction, Norm } from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

let jurCache: Jurisdiction[] | null = null;
let normCache: Norm[] | null = null;
let graphCache: Graph | null = null;

export function loadJurisdictions(): Jurisdiction[] {
  if (jurCache) return jurCache;
  const p = path.join(DATA_DIR, "jurisdicoes.json");
  if (!fs.existsSync(p)) return [];
  jurCache = JSON.parse(fs.readFileSync(p, "utf-8")) as Jurisdiction[];
  return jurCache;
}

export function loadNorms(): Norm[] {
  if (normCache) return normCache;
  const p = path.join(DATA_DIR, "normas.json");
  if (!fs.existsSync(p)) return [];
  normCache = JSON.parse(fs.readFileSync(p, "utf-8")) as Norm[];
  return normCache;
}

export function loadGraph(): Graph {
  if (graphCache) return graphCache;
  const p = path.join(DATA_DIR, "grafo.json");
  if (!fs.existsSync(p)) return { nodes: [], edges: [] };
  graphCache = JSON.parse(fs.readFileSync(p, "utf-8")) as Graph;
  return graphCache;
}

export function jurisdictionsByIso(): Record<string, Jurisdiction> {
  const out: Record<string, Jurisdiction> = {};
  for (const j of loadJurisdictions()) out[j.iso] = j;
  return out;
}
