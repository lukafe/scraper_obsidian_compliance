"use client";

import { useEffect, useState } from "react";
import {
  ComposableMap, Geographies, Geography, ZoomableGroup,
} from "react-simple-maps";
import { Jurisdiction, ISO2_TO_ISO3, ISO3_TO_ISO2 } from "@/lib/types";
import { opportunityScore } from "@/lib/scoring";

const TOPO_URL =
  "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json";

type Metric = "score" | "services" | "urgency" | "norms";

interface Props {
  data: Jurisdiction[];
}

export function WorldMap({ data }: Props) {
  const [metric, setMetric] = useState<Metric>("score");
  const [hovered, setHovered] = useState<Jurisdiction | null>(null);

  const byIso3 = new Map<string, Jurisdiction & { score: number }>();
  for (const j of data) {
    byIso3.set(ISO2_TO_ISO3[j.iso] ?? "", { ...j, score: opportunityScore(j) });
  }

  function colorFor(iso3: string): string {
    const j = byIso3.get(iso3);
    if (!j) return "#1A0F0F";
    let v: number;
    switch (metric) {
      case "score": v = j.score / 100; break;
      case "services": v = j.n_servicos / 14; break;
      case "urgency":
        v = j.urgencia_deadline_dias === null
          ? 0.1
          : Math.max(0, 1 - (j.urgencia_deadline_dias / 730));
        break;
      case "norms": v = Math.min(1, j.n_normas_total / 120); break;
    }
    return `rgba(232, 60, 50, ${0.15 + v * 0.85})`;
  }

  return (
    <div>
      {/* Metric selector */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {[
          ["score", "Opportunity Score"],
          ["services", "# Services Triggered"],
          ["urgency", "Deadline Urgency"],
          ["norms", "# Norms Tracked"],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setMetric(key as Metric)}
            className={`px-3 py-1.5 text-xs rounded border transition-colors ${
              metric === key
                ? "bg-certik-red text-white border-certik-red"
                : "bg-certik-panel text-zinc-300 border-certik-border hover:border-certik-red/50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="relative w-full h-[560px] bg-certik-dark border border-certik-border rounded">
        <ComposableMap
          projection="geoEqualEarth"
          projectionConfig={{ scale: 165 }}
          height={560}
          style={{ width: "100%", height: "100%" }}
        >
          <ZoomableGroup zoom={1} center={[0, 20]}>
            <Geographies geography={TOPO_URL}>
              {({ geographies }: { geographies: any[] }) =>
                geographies.map((geo) => {
                  const iso3 = geo.id || geo.properties.iso_a3;
                  const j = byIso3.get(iso3);
                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      fill={colorFor(iso3)}
                      stroke="#0F0808"
                      strokeWidth={0.5}
                      onMouseEnter={() => j && setHovered(j)}
                      onMouseLeave={() => setHovered(null)}
                      style={{
                        default: { outline: "none" },
                        hover: {
                          outline: "none", fill: j ? "#E83C32" : "#1A0F0F",
                          cursor: j ? "pointer" : "default",
                        },
                        pressed: { outline: "none" },
                      }}
                    />
                  );
                })
              }
            </Geographies>
          </ZoomableGroup>
        </ComposableMap>

        {/* Hover card */}
        {hovered && (
          <div className="absolute top-3 right-3 bg-certik-panel border border-certik-border rounded p-4 text-sm shadow-lg max-w-xs">
            <div className="font-bold text-white">{hovered.iso} — {hovered.pais}</div>
            <div className="text-certik-muted text-xs mt-1">{hovered.regiao}</div>
            <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
              <div className="text-certik-muted">Score:</div>
              <div className="text-certik-red font-mono text-right">
                {(opportunityScore(hovered)).toFixed(1)}
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
              <div className="text-right">{hovered.maturidade_mercado}</div>
              <div className="text-certik-muted">Lead reg:</div>
              <div className="text-right">{hovered.regulador_principal ?? "—"}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
