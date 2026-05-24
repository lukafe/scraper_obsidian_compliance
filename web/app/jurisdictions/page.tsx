import { loadJurisdictions } from "@/lib/data";
import { rankJurisdictions, urgencyColor, maturityColor } from "@/lib/scoring";
import { Card } from "@/components/ui/card";
import Link from "next/link";

export default function JurisdictionsList() {
  const ranked = rankJurisdictions(loadJurisdictions());

  // Group by region
  const byRegion = new Map<string, typeof ranked>();
  for (const j of ranked) {
    const k = j.regiao || "—";
    if (!byRegion.has(k)) byRegion.set(k, []);
    byRegion.get(k)!.push(j);
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold text-white">Jurisdictions</h1>
        <p className="text-certik-muted mt-1">
          All {ranked.length} jurisdictions, grouped by region and sorted by opportunity score.
        </p>
      </header>

      {Array.from(byRegion.entries()).map(([region, list]) => (
        <Card key={region} title={region} subtitle={`${list.length} jurisdictions`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {list.map((j) => (
              <Link key={j.iso} href={`/jurisdictions/${j.iso}`}>
                <div className="border border-certik-border rounded p-4 hover:border-certik-red transition-colors h-full">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-white font-semibold">{j.iso} — {j.pais}</div>
                      <div className="text-xs text-certik-muted mt-0.5">{j.regulador_principal ?? "—"}</div>
                    </div>
                    <span
                      className="px-2 py-0.5 rounded font-mono text-xs"
                      style={{
                        background: `rgba(232,60,50,${j.score / 100})`,
                        color: j.score > 60 ? "white" : "#FCC",
                      }}
                    >
                      {j.score.toFixed(0)}
                    </span>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <div className="text-certik-muted">Services</div>
                      <div className="text-white font-medium">{j.n_servicos}/14</div>
                    </div>
                    <div>
                      <div className="text-certik-muted">Days</div>
                      <div style={{ color: urgencyColor(j.urgencia_deadline_dias) }}>
                        {j.urgencia_deadline_dias ?? "—"}
                      </div>
                    </div>
                    <div>
                      <div className="text-certik-muted">Maturity</div>
                      <div style={{ color: maturityColor(j.maturidade_mercado) }}>
                        {j.maturidade_mercado}
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}
