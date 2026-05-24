import { loadJurisdictions, loadNorms } from "@/lib/data";
import { Card, Kpi } from "@/components/ui/card";
import { rankJurisdictions, urgencyColor, maturityColor } from "@/lib/scoring";
import { SERVICE_CATEGORIES, SERVICE_LABELS } from "@/lib/types";
import { label } from "@/lib/labels";
import Link from "next/link";

interface Props {
  searchParams: Promise<{ focus?: string }>;
}

export default async function ServicesPage({ searchParams }: Props) {
  const params = await searchParams;
  const focus = params.focus;
  const juris = loadJurisdictions();
  const norms = loadNorms();

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold text-white">By CertiK Service</h1>
        <p className="text-certik-muted mt-1">
          For each security service, see which jurisdictions trigger it and how attractive each market is right now.
        </p>
      </header>

      {/* Category overview */}
      {!focus && (
        <div className="space-y-6">
          {Object.entries(SERVICE_CATEGORIES).map(([cat, services]) => (
            <div key={cat}>
              <h2 className="text-lg font-semibold text-white mb-3">{cat}</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {services.map((s) => {
                  const triggers = juris.filter((j) => j.servicos.includes(s));
                  const top = rankJurisdictions(triggers)[0];
                  return (
                    <Link key={s} href={`/services?focus=${s}`}>
                      <Card className="hover:border-certik-red transition-colors cursor-pointer">
                        <h3 className="font-semibold text-white">{SERVICE_LABELS[s] ?? s}</h3>
                        <div className="mt-2 text-2xl font-bold text-certik-red">
                          {triggers.length} <span className="text-sm text-certik-muted">/ {juris.length} juris</span>
                        </div>
                        {top && (
                          <div className="mt-2 text-xs text-certik-muted">
                            Top: <span className="text-white">{top.iso}</span>
                            <span className="text-zinc-400"> · {top.score.toFixed(1)}</span>
                          </div>
                        )}
                      </Card>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Focus view */}
      {focus && (() => {
        const serviceName = SERVICE_LABELS[focus] ?? focus;
        const inScope = juris.filter((j) => j.servicos.includes(focus));
        const ranked = rankJurisdictions(inScope);
        const normsWith = norms.filter((n) => n.servicos.includes(focus));

        return (
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-semibold text-white">{serviceName}</h2>
              <Link href="/services" className="text-sm text-certik-muted hover:text-certik-red">
                ← back to all services
              </Link>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <Kpi label="Jurisdictions triggering" value={inScope.length} accent />
              <Kpi label="Norms triggering" value={normsWith.length} />
              <Kpi
                label="High-maturity markets"
                value={inScope.filter((j) => j.maturidade_mercado === "alta").length}
              />
            </div>

            <Card title={`Top markets for ${serviceName}`}>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-certik-muted border-b border-certik-border">
                    <th className="py-2 px-3 font-medium">Country</th>
                    <th className="py-2 px-3 font-medium">Region</th>
                    <th className="py-2 px-3 font-medium">Lead regulator</th>
                    <th className="py-2 px-3 font-medium">Maturity</th>
                    <th className="py-2 px-3 font-medium">Next deadline</th>
                    <th className="py-2 px-3 text-right font-medium">Days</th>
                    <th className="py-2 px-3 text-right font-medium">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((j) => (
                    <tr key={j.iso} className="border-b border-certik-border/40 hover:bg-certik-border/20">
                      <td className="py-2 px-3">
                        <Link href={`/jurisdictions/${j.iso}`} className="text-white hover:text-certik-red font-medium">
                          {j.iso} — {j.pais}
                        </Link>
                      </td>
                      <td className="py-2 px-3 text-zinc-400">{j.regiao}</td>
                      <td className="py-2 px-3 text-zinc-400">{j.regulador_principal ?? "—"}</td>
                      <td className="py-2 px-3">
                        <span style={{ color: maturityColor(j.maturidade_mercado) }}>
                          {label.maturity(j.maturidade_mercado)}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-zinc-400">{j.deadline_principal ?? "—"}</td>
                      <td className="py-2 px-3 text-right" style={{ color: urgencyColor(j.urgencia_deadline_dias) }}>
                        {j.urgencia_deadline_dias ?? "—"}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-certik-red">{j.score.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <Card title={`Norms that trigger ${serviceName}`}>
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {normsWith.map((n) => (
                  <div key={n.id} className="border-b border-certik-border/30 pb-2 last:border-0">
                    <div className="flex items-center justify-between gap-2">
                      <Link href={`/jurisdictions/${n.country}`} className="text-xs text-certik-muted hover:text-certik-red">
                        {n.country}
                      </Link>
                      <span className="text-xs text-zinc-500">{n.date ?? ""}</span>
                    </div>
                    <div className="text-sm text-white">{n.title}</div>
                    {n.escopo && <p className="text-xs text-zinc-400 mt-1">{n.escopo}</p>}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        );
      })()}
    </div>
  );
}
