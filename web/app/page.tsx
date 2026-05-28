import Link from "next/link";
import { loadJurisdictions } from "@/lib/data";
import { rankJurisdictions, maturityColor, urgencyColor } from "@/lib/scoring";
import { Card, Kpi } from "@/components/ui/card";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { ScoreChip } from "@/components/ui/score-chip";
import { SERVICE_LABELS, SERVICE_CATEGORIES } from "@/lib/types";
import { label } from "@/lib/labels";

export default function HomePage() {
  const juris = loadJurisdictions();
  const ranked = rankJurisdictions(juris);

  const verifiedDeadlines = juris.filter(
    (j) => j.urgencia_deadline_dias !== null && j.urgencia_deadline_dias >= 0,
  );
  const upcomingYear = verifiedDeadlines.filter(
    (j) => (j.urgencia_deadline_dias ?? 0) <= 365,
  ).length;
  const matureMarkets = juris.filter((j) => j.maturidade_mercado === "alta").length;
  const totalNorms = juris.reduce((acc, j) => acc + j.n_normas_total, 0);

  // Aggregate service demand
  const serviceCount = new Map<string, number>();
  for (const j of juris) {
    for (const s of j.servicos) serviceCount.set(s, (serviceCount.get(s) ?? 0) + 1);
  }
  const topServices = [...serviceCount.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  const top3 = ranked.slice(0, 3);

  return (
    <div className="space-y-10">
      <header className="border-b border-certik-border pb-6">
        <h1 className="text-3xl font-semibold text-white tracking-tight">
          Where to expand. What to sell first.
        </h1>
        <p className="mt-3 text-certik-muted max-w-3xl leading-relaxed">
          {juris.length} jurisdictions ranked by a composite opportunity score combining
          regulatory urgency, the intensity of CertiK services triggered by local rules, and
          market maturity. Top three picks below — click any card for the full country profile.
        </p>
      </header>

      {/* ---------- Hero: top 3 picks ---------- */}
      <section>
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
            Recommended next moves
          </h2>
          <Link
            href="/jurisdictions"
            className="text-xs text-certik-muted hover:text-certik-red"
          >
            See all {juris.length} jurisdictions →
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {top3.map((j, i) => (
            <Link key={j.iso} href={`/jurisdictions/${j.iso}`} className="group">
              <article className="h-full bg-certik-panel border border-certik-border rounded-lg p-5 hover:border-certik-red/70 transition-colors">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[10px] font-mono text-certik-muted uppercase tracking-widest">
                      Pick #{i + 1}
                    </div>
                    <h3 className="mt-1 text-xl font-semibold text-white group-hover:text-certik-red transition-colors truncate">
                      {j.pais}
                    </h3>
                    <div className="text-xs text-certik-muted mt-0.5">
                      {j.iso} · {j.regiao}
                    </div>
                  </div>
                  <ScoreChip score={j.score} size="md" />
                </div>

                <dl className="mt-4 space-y-1.5 text-xs">
                  <Row label="Lead regulator" value={j.regulador_principal ?? "—"} />
                  <Row
                    label="Next deadline"
                    value={
                      j.deadline_principal ? (
                        <span style={{ color: urgencyColor(j.urgencia_deadline_dias) }}>
                          {j.deadline_principal}
                          {j.urgencia_deadline_dias !== null && (
                            <span className="text-certik-muted ml-1">
                              ({j.urgencia_deadline_dias}d)
                            </span>
                          )}
                          {j.tipo_deadline && (
                            <span className="text-certik-muted ml-1">
                              · {label.deadlineType(j.tipo_deadline)}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span
                          className="text-certik-muted"
                          title="No body-grounded deadline extracted yet for this jurisdiction."
                        >
                          none verified
                        </span>
                      )
                    }
                  />
                  <Row
                    label="Services triggered"
                    value={
                      <span>
                        <span className="text-white font-mono">{j.n_servicos}</span>
                        <span className="text-certik-muted"> / 14</span>
                      </span>
                    }
                  />
                  <Row
                    label="Maturity"
                    value={
                      <span style={{ color: maturityColor(j.maturidade_mercado) }}>
                        {label.maturity(j.maturidade_mercado)}
                        <span className="text-certik-muted ml-1">
                          ({j.n_cobertura}/6)
                        </span>
                      </span>
                    }
                  />
                </dl>

                {j.servicos.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-certik-border/60">
                    <div className="text-[10px] text-certik-muted uppercase tracking-wide mb-1.5">
                      Top services to sell
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {j.servicos.slice(0, 4).map((s) => (
                        <span
                          key={s}
                          className="inline-block px-2 py-0.5 rounded text-[10px] bg-certik-red/15 border border-certik-red/30 text-certik-red"
                        >
                          {SERVICE_LABELS[s] ?? s}
                        </span>
                      ))}
                      {j.servicos.length > 4 && (
                        <span className="text-[10px] text-certik-muted self-center">
                          +{j.servicos.length - 4} more
                        </span>
                      )}
                    </div>
                  </div>
                )}

                <div className="mt-4 flex items-center justify-between">
                  <ConfidenceBadge confidence={j.data_confidence} />
                  <span className="text-xs text-certik-muted group-hover:text-certik-red transition-colors">
                    Country profile →
                  </span>
                </div>
              </article>
            </Link>
          ))}
        </div>
      </section>

      {/* ---------- Quick stats strip ---------- */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Jurisdictions tracked" value={juris.length} accent />
        <Kpi
          label="Norms tracked"
          value={totalNorms.toLocaleString()}
          hint="Source-cited statutes, regulations & guidance"
        />
        <Kpi
          label="Verified upcoming deadlines"
          value={verifiedDeadlines.length}
          hint={
            upcomingYear > 0
              ? `${upcomingYear} within the next 12 months`
              : "Body-grounded, with verbatim quote"
          }
        />
        <Kpi
          label="High-maturity markets"
          value={matureMarkets}
          hint="5+ of 6 regulatory dimensions covered"
        />
      </div>

      {/* ---------- Top 3 services ---------- */}
      <Card
        title="Top services in demand"
        subtitle="The three CertiK services triggered by the largest share of jurisdictions — start the portfolio here."
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {topServices.map(([service, count], i) => {
            const pct = (count / juris.length) * 100;
            return (
              <Link
                key={service}
                href={`/services?focus=${service}`}
                className="group block border border-certik-border rounded-lg p-4 hover:border-certik-red/60 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[10px] font-mono text-certik-muted uppercase tracking-widest">
                      #{i + 1} in demand
                    </div>
                    <div className="text-base font-semibold text-white mt-1 truncate">
                      {SERVICE_LABELS[service] ?? service}
                    </div>
                  </div>
                  <div className="text-2xl font-mono text-certik-red shrink-0">
                    {count}
                  </div>
                </div>
                <div className="mt-3 bg-certik-border/30 rounded h-1.5 overflow-hidden">
                  <div className="h-full bg-certik-red" style={{ width: `${pct}%` }} />
                </div>
                <div className="mt-1 flex justify-between text-[11px] text-certik-muted">
                  <span>{count} of {juris.length} jurisdictions</span>
                  <span className="opacity-0 group-hover:opacity-100 transition-opacity">
                    breakdown →
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </Card>

      {/* ---------- Full ranking table ---------- */}
      <Card
        title="Top opportunities — full ranking"
        subtitle="Top 12 markets by composite opportunity score (0 to 100). Click a row for the full country profile."
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
                    <ScoreChip score={j.score} />
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

      {/* ---------- All service demand ---------- */}
      <Card
        title="All services — demand breakdown"
        subtitle="Share of jurisdictions whose rules trigger each CertiK service, grouped by category."
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
                      className="group grid grid-cols-12 items-center gap-2 text-xs hover:bg-certik-border/20 px-2 py-1.5 rounded transition-colors"
                    >
                      <span className="col-span-4 text-zinc-300 group-hover:text-white">
                        {SERVICE_LABELS[s] ?? s}
                      </span>
                      <div className="col-span-6 bg-certik-border/30 rounded h-2 overflow-hidden">
                        <div
                          className="h-full bg-certik-red transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="col-span-2 text-right text-certik-muted font-mono flex items-center justify-end gap-1">
                        {count}/{juris.length}
                        <span
                          aria-hidden
                          className="text-certik-muted opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          ›
                        </span>
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

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-certik-muted shrink-0">{label}</dt>
      <dd className="text-right truncate text-zinc-200">{value}</dd>
    </div>
  );
}
