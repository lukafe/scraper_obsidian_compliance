"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { geoEqualEarth, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { feature } from "topojson-client";
import type { Topology, GeometryObject } from "topojson-specification";
import { Jurisdiction, ISO2_TO_ISO3 } from "@/lib/types";
import { opportunityScore } from "@/lib/scoring";
import { label } from "@/lib/labels";

const TOPO_URL =
  "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json";

type Metric = "score" | "services" | "urgency" | "norms";

const METRICS: { key: Metric; label: string }[] = [
  { key: "score", label: "Opportunity score" },
  { key: "services", label: "Services triggered" },
  { key: "urgency", label: "Deadline urgency" },
  { key: "norms", label: "Norms tracked" },
];

// Numeric IDs in world-atlas 110m are UN M.49 codes — map ISO3 -> M.49.
// Source: https://github.com/topojson/world-atlas
// We only need entries for countries that exist in our jurisdiction set.
const ISO3_TO_M49: Record<string, string> = {
  BRA: "076", ARG: "032", MEX: "484", URY: "858",
  USA: "840", CAN: "124", BMU: "060",
  DEU: "276", FRA: "250", ITA: "380", LTU: "440", GBR: "826",
  CHE: "756",
  SGP: "702", JPN: "392", HKG: "344", KOR: "410",
  IND: "356", ARE: "784", TUR: "792",
  ZAF: "710", NGA: "566", SWE: "752",
};

interface CountryFeature {
  type: "Feature";
  id: string;
  properties: { name: string };
  geometry: GeometryObject;
}

interface Props {
  data: Jurisdiction[];
}

export function WorldMap({ data }: Props) {
  const [metric, setMetric] = useState<Metric>("score");
  const [hovered, setHovered] = useState<Jurisdiction | null>(null);
  const [features, setFeatures] = useState<CountryFeature[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch the world topology once on the client.
  useEffect(() => {
    let cancelled = false;
    fetch(TOPO_URL)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((topo: Topology) => {
        if (cancelled) return;
        const countries = topo.objects.countries as GeometryObject;
        const fc = feature(topo, countries) as {
          type: "FeatureCollection";
          features: CountryFeature[];
        };
        setFeatures(fc.features);
      })
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  // Lookup by ISO3 (faster than rebuilding inside paint).
  const byIso3 = useMemo(() => {
    const m = new Map<string, Jurisdiction & { score: number }>();
    for (const j of data) {
      const iso3 = ISO2_TO_ISO3[j.iso];
      if (iso3) m.set(iso3, { ...j, score: opportunityScore(j) });
    }
    return m;
  }, [data]);

  // Reverse map UN M.49 -> ISO3 (only for our 23 jurisdictions).
  const m49ToIso3 = useMemo(() => {
    const m = new Map<string, string>();
    for (const [iso3, m49] of Object.entries(ISO3_TO_M49)) m.set(m49, iso3);
    return m;
  }, []);

  const projection = useMemo(
    () => geoEqualEarth().scale(160).translate([480, 270]),
    [],
  );
  const pathGen = useMemo(() => geoPath(projection), [projection]);

  function colorFor(iso3: string | undefined): string {
    if (!iso3) return "#1A0F0F";
    const j = byIso3.get(iso3);
    if (!j) return "#1A0F0F";
    let v: number;
    switch (metric) {
      case "score":
        v = j.score / 100;
        break;
      case "services":
        v = j.n_servicos / 14;
        break;
      case "urgency":
        v =
          j.urgencia_deadline_dias === null
            ? 0.1
            : Math.max(0, 1 - j.urgencia_deadline_dias / 730);
        break;
      case "norms":
        v = Math.min(1, j.n_normas_total / 120);
        break;
    }
    return `rgba(232, 60, 50, ${0.18 + v * 0.82})`;
  }

  return (
    <div>
      {/* Metric selector */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {METRICS.map(({ key, label: btnLabel }) => (
          <button
            key={key}
            onClick={() => setMetric(key)}
            className={`px-3 py-1.5 text-xs rounded border transition-colors ${
              metric === key
                ? "bg-certik-red text-white border-certik-red"
                : "bg-certik-panel text-zinc-300 border-certik-border hover:border-certik-red/50"
            }`}
          >
            {btnLabel}
          </button>
        ))}
      </div>

      <div className="relative w-full h-[560px] bg-certik-dark border border-certik-border rounded-lg overflow-hidden">
        {error && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-amber-300/80 p-6 text-center">
            Could not load the world topology from CDN: {error}.
            <br />
            The map needs network access on first load.
          </div>
        )}
        {!features && !error && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-certik-muted">
            Loading map…
          </div>
        )}
        {features && (
          <svg
            viewBox="0 0 960 540"
            preserveAspectRatio="xMidYMid meet"
            className="w-full h-full"
          >
            <g>
              {features.map((f) => {
                const iso3 = m49ToIso3.get(String(f.id));
                const j = iso3 ? byIso3.get(iso3) : undefined;
                const d = pathGen(f as unknown as GeoPermissibleObjects);
                if (!d) return null;
                const isHovered = j && hovered?.iso === j.iso;
                return (
                  <path
                    key={f.id}
                    d={d}
                    fill={isHovered ? "#E83C32" : colorFor(iso3)}
                    stroke="#0F0808"
                    strokeWidth={0.5}
                    onMouseEnter={() => j && setHovered(j)}
                    onMouseLeave={() => setHovered(null)}
                    style={{
                      cursor: j ? "pointer" : "default",
                      transition: "fill 80ms linear",
                    }}
                  />
                );
              })}
            </g>
          </svg>
        )}

        {/* Hover card */}
        {hovered && (
          <div className="absolute top-3 right-3 bg-certik-panel border border-certik-border rounded p-4 text-sm shadow-lg max-w-xs pointer-events-none">
            <div className="font-bold text-white">
              {hovered.iso} — {hovered.pais}
            </div>
            <div className="text-certik-muted text-xs mt-1">{hovered.regiao}</div>
            <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
              <div className="text-certik-muted">Score:</div>
              <div className="text-certik-red font-mono text-right">
                {opportunityScore(hovered).toFixed(1)}
              </div>
              <div className="text-certik-muted">Services:</div>
              <div className="text-right">{hovered.n_servicos}/14</div>
              <div className="text-certik-muted">Deadline:</div>
              <div className="text-right">
                {hovered.urgencia_deadline_dias !== null
                  ? `${hovered.urgencia_deadline_dias} days`
                  : "—"}
              </div>
              <div className="text-certik-muted">Maturity:</div>
              <div className="text-right">{label.maturity(hovered.maturidade_mercado)}</div>
              <div className="text-certik-muted">Lead regulator:</div>
              <div className="text-right">{hovered.regulador_principal ?? "—"}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
