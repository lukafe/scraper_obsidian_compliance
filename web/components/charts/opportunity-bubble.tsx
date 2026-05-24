"use client";

import {
  ResponsiveContainer, ScatterChart, Scatter,
  XAxis, YAxis, ZAxis, Tooltip, Cell, ReferenceLine, Label,
} from "recharts";
import { Jurisdiction } from "@/lib/types";
import { maturityColor, opportunityScore } from "@/lib/scoring";
import { label } from "@/lib/labels";

interface Point {
  iso: string; pais: string; x: number; y: number;
  z: number; maturity: string; score: number;
}

export function OpportunityBubble({ data }: { data: Jurisdiction[] }) {
  const points: Point[] = data.map((j) => ({
    iso: j.iso, pais: j.pais,
    x: j.n_servicos,
    y: j.urgencia_deadline_dias ?? 900,
    z: Math.max(60, j.n_normas_total * 6),
    maturity: j.maturidade_mercado ?? "desconhecido",
    score: opportunityScore(j),
  }));

  return (
    <div className="w-full h-[560px]">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 20, right: 30, bottom: 40, left: 30 }}>
          {/* Quadrant guides */}
          <ReferenceLine x={7} stroke="#444" strokeDasharray="4 4" />
          <ReferenceLine y={180} stroke="#444" strokeDasharray="4 4" />

          <XAxis
            type="number" dataKey="x" name="CertiK services triggered"
            domain={[0, 14]}
            stroke="#8A6E6E"
            tick={{ fill: "#A78A8A" }}
          >
            <Label value="CertiK services triggered (0–14)" offset={-25}
                   position="insideBottom" fill="#A78A8A" />
          </XAxis>
          <YAxis
            type="number" dataKey="y" name="Days until next deadline"
            domain={[0, 900]} reversed
            stroke="#8A6E6E"
            tick={{ fill: "#A78A8A" }}
          >
            <Label value="Days until next deadline (lower = more urgent)"
                   angle={-90} position="insideLeft" fill="#A78A8A"
                   style={{ textAnchor: "middle" }} offset={-10} />
          </YAxis>
          <ZAxis type="number" dataKey="z" range={[60, 600]} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload || !payload.length) return null;
              const p = payload[0].payload as Point;
              return (
                <div className="bg-certik-panel border border-certik-border rounded p-3 text-xs">
                  <div className="font-semibold text-white">{p.iso} — {p.pais}</div>
                  <div className="text-certik-muted mt-1">Services: {p.x}/14</div>
                  <div className="text-certik-muted">Days to deadline: {p.y === 900 ? "n/a" : Math.round(p.y)}</div>
                  <div className="text-certik-muted">Maturity: {label.maturity(p.maturity)}</div>
                  <div className="text-certik-red font-mono mt-1">Score: {p.score.toFixed(1)}</div>
                </div>
              );
            }}
          />
          <Scatter name="Jurisdictions" data={points}>
            {points.map((p, i) => (
              <Cell key={i} fill={maturityColor(p.maturity)} fillOpacity={0.7}
                    stroke={maturityColor(p.maturity)} strokeWidth={1.5} />
            ))}
          </Scatter>

          {/* Quadrant labels */}
          <text x="78%" y="14%" fill="#E83C32" fontSize="13" fontWeight="600">
            Act now — broad and urgent
          </text>
          <text x="20%" y="14%" fill="#FFB300" fontSize="12">
            Urgent — narrow scope
          </text>
          <text x="75%" y="92%" fill="#FFE066" fontSize="12">
            Strategic pipeline
          </text>
          <text x="22%" y="92%" fill="#888" fontSize="12">
            Monitor — low priority
          </text>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
