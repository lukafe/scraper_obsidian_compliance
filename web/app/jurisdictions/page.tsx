import { loadJurisdictions } from "@/lib/data";
import { rankJurisdictions, urgencyColor, maturityColor } from "@/lib/scoring";
import { Card } from "@/components/ui/card";
import { ScoreChip } from "@/components/ui/score-chip";
import { label } from "@/lib/labels";
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
      <header className="border-b border-certik-border pb-6">
        <h1 className="text-3xl font-semibold text-white tracking-tight">Jurisdictions</h1>
        <p className="text-certik-muted mt-2 max-w-3xl leading-relaxed">
          All {ranked.length} jurisdictions, grouped by region and sorted by opportunity score.
        </p>
      </header>

      {Array.from(byRegion.entries()).map(([region, list]) => (
        <Card key={region} title={region} subtitle={`${list.length} jurisdictions`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {list.map((j) => (
              <Link key={j.iso} href={`/jurisdictions/${j.iso}`} className="group">
                <div className="border border-certik-border rounded-lg p-4 hover:border-certik-red/70 hover:bg-certik-border/10 transition-colors h-full">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-white font-semibold truncate">
                        {j.iso} — {j.pais}
                      </div>
                      <div className="text-xs text-certik-muted mt-0.5 truncate">
                        {j.regulador_principal ?? "—"}
                      </div>
                    </div>
                    <ScoreChip score={j.score} />
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <div className="text-certik-muted uppercase tracking-wide text-[10px]">Services</div>
                      <div className="text-white font-medium mt-0.5">{j.n_servicos}/14</div>
                    </div>
                    <div>
                      <div className="text-certik-muted uppercase tracking-wide text-[10px]">Days</div>
                      <div className="mt-0.5" style={{ color: urgencyColor(j.urgencia_deadline_dias) }}>
                        {j.urgencia_deadline_dias ?? "—"}
                      </div>
                    </div>
                    <div>
                      <div className="text-certik-muted uppercase tracking-wide text-[10px]">Maturity</div>
                      <div className="mt-0.5" style={{ color: maturityColor(j.maturidade_mercado) }}>
                        {label.maturity(j.maturidade_mercado)}
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
