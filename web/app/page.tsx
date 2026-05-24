import Link from "next/link";
import { loadJurisdictions } from "@/lib/data";
import { rankJurisdictions, opportunityScore, maturityColor, urgencyColor } from "@/lib/scoring";
import { Card, Kpi } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { OpportunityBubble } from "@/components/charts/opportunity-bubble";
import { SERVICE_LABELS, SERVICE_CATEGORIES } from "@/lib/types";

export default function HomePage() {
  const juris = loadJurisdictions();
  const ranked = rankJurisdictions(juris);

  const upcoming30 = juris.filter(
    (j) => j.urgencia_deadline_dias !== null && j.urgencia_deadline_dias >= 0 && j.urgencia_deadline_dias <= 30
  ).length;
  const upcoming180 = juris.filter(
    (j) => j.urgencia_deadline_dias !== null && j.urgencia_deadline_dias >= 0 && j.urgencia_deadline_dias <= 180
  ).length;
  const matureMarkets = juris.filter((j) => j.maturidade_mercado === "alta").length;

  // Aggregate service demand
  const serviceCount = new Map<string, number>();
  for (const j of juris) {
    for (const s of j.servicos) serviceCount.set(s, (serviceCount.get(s) ?? 0) + 1);
  }
  const sortedServices = Array.from(serviceCount.entries()).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-white">Where to expand. What to sell first.</h1>
        <p className="mt-2 text-certik-muted max-w-3xl">
          {juris.length} jurisdictions ranked by opportunity score — a composite of regulatory urgency,
          intensity of CertiK services triggered, and market maturity. Click any row to drill down.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Jurisdictions tracked" value={juris.length} accent />
        <Kpi label="Deadlines ≤ 30 days" value={upcoming30}
             hint={upcoming30 > 0 ? "Sell now" : undefined} />
        <Kpi label="Deadlines ≤ 180 days" value={upcoming180} />
        <Kpi label="Mature markets" value={matureMarkets}
             hint="`maturidade: alta`" />
      </div>

      <Card
        title="🎯 The Money Chart — Urgency × Service Intensity"
        subtitle="Bubble = jurisdiction. Size = # of norms tracked. Color = market maturity (green/amber/red = alta/media/baixa)."
      >
        <OpportunityBubble data={juris} />
      </Card>

      <Card title="🏆 Top opportunities" subtitle="Ranked by composite opportunity score (0–100).">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-certik-muted border-b border-certik-border">
                <th className="py-2 px-3">#</th>
                <th className="py-2 px-3">Country</th>
                <th className="py-2 px-3">Region</th>
                <th className="py-2 px-3">Lead Regulator</th>
                <th className="py-2 px-3">Next Deadline</th>
                <th className="py-2 px-3 text-right">Days</th>
                <th className="py-2 px-3 text-right"># Services</th>
                <th className="py-2 px-3">Maturity</th>
                <th className="py-2 px-3 text-right">Score</th>
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
                    <Link href={`/jurisdictions/${j.iso}`} className="text-white hover:text-certik-red font-medium">
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
                      {j.maturidade_mercado}
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card
        title="🛠 Aggregated service demand"
        subtitle="How many jurisdictions trigger each security service."
      >
        <div className="space-y-4">
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
