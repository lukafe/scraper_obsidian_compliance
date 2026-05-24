import Link from "next/link";
import { loadJurisdictions } from "@/lib/data";
import { rankJurisdictions, maturityColor, urgencyColor } from "@/lib/scoring";
import { Card, Kpi } from "@/components/ui/card";
import { OpportunityBubble } from "@/components/charts/opportunity-bubble";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { SERVICE_LABELS, SERVICE_CATEGORIES } from "@/lib/types";
import { label } from "@/lib/labels";

export default function HomePage() {
  const juris = loadJurisdictions();
  const ranked = rankJurisdictions(juris);

  const upcoming30 = juris.filter(
    (j) => j.urgencia_deadline_dias !== null && j.urgencia_deadline_dias >= 0 && j.urgencia_deadline_dias <= 30,
  ).length;
  const upcoming180 = juris.filter(
    (j) => j.urgencia_deadline_dias !== null && j.urgencia_deadline_dias >= 0 && j.urgencia_deadline_dias <= 180,
  ).length;
  const matureMarkets = juris.filter((j) => j.maturidade_mercado === "alta").length;

  const serviceCount = new Map<string, number>();
  for (const j of juris) {
    for (const s of j.servicos) serviceCount.set(s, (serviceCount.get(s) ?? 0) + 1);
  }

  return (
    <div className="space-y-10">
      <header className="border-b border-certik-border pb-6">
        <h1 className="text-3xl font-semibold text-white tracking-tight">
          Where to expand. What to sell first.
        </h1>
        <p className="mt-3 text-certik-muted max-w-3xl leading-relaxed">
          {juris.length} jurisdictions ranked by a composite opportunity score combining regulatory
          urgency, the intensity of CertiK services triggered by local rules, and market maturity.
          Click any row to open the full country profile.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Jurisdictions tracked" value={juris.length} accent />
        <Kpi
          label="Deadlines within 30 days"
          value={upcoming30}
          hint={upcoming30 > 0 ? "Immediate sales window" : undefined}
        />
        <Kpi label="Deadlines within 180 days" value={upcoming180} />
        <Kpi label="High-maturity markets" value={matureMarkets} hint="Heuristic — see methodology" />
      </div>

      <Card
        title="Opportunity matrix"
        subtitle="X axis: CertiK services triggered. Y axis: days to the next regulatory deadline (lower is more urgent). Bubble size: total norms tracked. Colour: market maturity."
      >
        <OpportunityBubble data={juris} />
      </Card>

      <Card
        title="Top opportunities"
        subtitle="Top 12 markets ranked by composite opportunity score (0 to 100)."
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-certik-muted border-b border-certik-border">
                <th className="py-2 px-3 font-medium">#</th>
                <th className="py-2 px-3 font-medium">Country</th>
                <th className="py-2 px-3 font-medium">Region</th>
                <th className="py-2 px-3 font-medium">Lead regulator</th>
                <th className="py-2 px-3 font-medium">Next deadline</th>
                <th className="py-2 px-3 text-right font-medium">Days</th>
                <th className="py-2 px-3 text-right font-medium">Services</th>
                <th className="py-2 px-3 font-medium">Maturity</th>
                <th className="py-2 px-3 text-right font-medium">Score</th>
                <th className="py-2 px-3 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {ranked.slice(0, 12).map((j, i) => (
                <tr
                  key={j.iso}
                  className="border-b border-certik-border/50 hover:bg-certik-border/20 transition-colors"
                >
                  <td className="py-2 px-3 text-certik-muted">{i + 1}</td>
                  <td className="py-2 px-3">
                    <Link
                      href={`/jurisdictions/${j.iso}`}
                      className="text-white hover:text-certik-red font-medium"
                    >
                      {j.iso} — {j.pais}
                    </Link>
                  </td>
                  <td className="py-2 px-3 text-zinc-400">{j.regiao}</td>
                  <td className="py-2 px-3 text-zinc-400">{j.regulador_principal ?? "—"}</td>
                  <td className="py-2 px-3 text-zinc-400">{j.deadline_principal ?? "—"}</td>
                  <td className="py-2 px-3 text-right">
                    <span style={{ color: urgencyColor(j.urgencia_deadline_dias) }}>
                      {j.urgencia_deadline_dias ?? "—"}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right">{j.n_servicos}</td>
                  <td className="py-2 px-3">
                    <span style={{ color: maturityColor(j.maturidade_mercado) }}>
                      {label.maturity(j.maturidade_mercado)}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right">
                    <span
                      className="px-2 py-0.5 rounded font-mono text-xs"
                      style={{
                        background: `rgba(232,60,50,${j.score / 100})`,
                        color: j.score > 60 ? "white" : "#FCC",
                      }}
                    >
                      {j.score.toFixed(1)}
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    <ConfidenceBadge confidence={j.data_confidence} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card
        title="Aggregated service demand"
        subtitle="Share of jurisdictions whose rules trigger each CertiK service."
      >
        <div className="space-y-5">
          {Object.entries(SERVICE_CATEGORIES).map(([cat, services]) => (
            <div key={cat}>
              <h4 className="text-sm font-semibold text-white mb-2">{cat}</h4>
              <div className="space-y-1">
                {services.map((s) => {
                  const count = serviceCount.get(s) ?? 0;
                  const pct = (count / juris.length) * 100;
                  return (
                    <Link
                      key={s}
                      href={`/services?focus=${s}`}
                      className="grid grid-cols-12 items-center gap-2 text-xs hover:bg-certik-border/20 px-2 py-1 rounded transition-colors"
                    >
                      <span className="col-span-4 text-zinc-300">{SERVICE_LABELS[s] ?? s}</span>
                      <div className="col-span-6 bg-certik-border/30 rounded h-2 overflow-hidden">
                        <div className="h-full bg-certik-red" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="col-span-2 text-right text-certik-muted font-mono">
                        {count}/{juris.length}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
