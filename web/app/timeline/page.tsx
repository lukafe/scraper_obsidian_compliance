import { loadNorms } from "@/lib/data";
import { Card, Kpi } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { urgencyBucket, urgencyColor } from "@/lib/scoring";
import Link from "next/link";

export default function TimelinePage() {
  const norms = loadNorms()
    .filter((n) => n.deadline_principal && !n.in_quarantine)
    .sort((a, b) => (a.deadline_principal ?? "").localeCompare(b.deadline_principal ?? ""));

  const past = norms.filter((n) => (n.urgencia_deadline_dias ?? 0) < 0).length;
  const next90 = norms.filter((n) => (n.urgencia_deadline_dias ?? -1) >= 0 && (n.urgencia_deadline_dias ?? 0) <= 90).length;
  const nextYear = norms.filter((n) => (n.urgencia_deadline_dias ?? -1) >= 0 && (n.urgencia_deadline_dias ?? 0) <= 365).length;

  // Group by country
  const byCountry = new Map<string, typeof norms>();
  for (const n of norms) {
    if (!byCountry.has(n.country)) byCountry.set(n.country, []);
    byCountry.get(n.country)!.push(n);
  }
  const countries = Array.from(byCountry.entries())
    .sort((a, b) => {
      const minA = Math.min(...a[1].map((n) => n.urgencia_deadline_dias ?? Infinity));
      const minB = Math.min(...b[1].map((n) => n.urgencia_deadline_dias ?? Infinity));
      return minA - minB;
    });

  return (
    <div className="space-y-6">
      <header className="border-b border-certik-border pb-6">
        <h1 className="text-3xl font-semibold text-white tracking-tight">Deadline timeline</h1>
        <p className="text-certik-muted mt-2 max-w-3xl leading-relaxed">
          Every regulatory deadline extracted from the source norms. Grouped by country and ordered
          by urgency — the smaller the day count, the closer the deadline.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Deadlines mapped" value={norms.length} accent />
        <Kpi label="Past due" value={past} />
        <Kpi label="Within 90 days" value={next90} />
        <Kpi label="Within 1 year" value={nextYear} />
      </div>

      <Card title="By country" subtitle="Ordered by the most urgent deadline in each jurisdiction.">
        <div className="space-y-4">
          {countries.map(([country, list]) => (
            <div key={country} className="border-b border-certik-border/30 pb-3 last:border-0">
              <div className="flex items-center justify-between mb-2">
                <Link
                  href={`/jurisdictions/${country}`}
                  className="text-white font-semibold hover:text-certik-red"
                >
                  {country}
                </Link>
                <span className="text-certik-muted text-xs">{list.length} deadlines</span>
              </div>
              <div className="space-y-1">
                {list.map((n) => {
                  const bucket = urgencyBucket(n.urgencia_deadline_dias);
                  const variant =
                    bucket === "past" ? "gray" :
                    bucket === "<= 90 days" ? "red" :
                    bucket === "<= 1 year" ? "amber" :
                    bucket === "> 1 year" ? "green" : "gray";
                  return (
                    <div key={n.id} className="flex items-start gap-3 text-xs py-1">
                      <span className="text-certik-muted font-mono w-24 shrink-0">
                        {n.deadline_principal}
                      </span>
                      <Badge variant={variant as any}>
                        {n.urgencia_deadline_dias === null
                          ? "—"
                          : n.urgencia_deadline_dias < 0
                            ? `${Math.abs(n.urgencia_deadline_dias)}d ago`
                            : `${n.urgencia_deadline_dias}d`}
                      </Badge>
                      <span className="text-zinc-300 flex-1 min-w-0 truncate" title={n.title}>
                        {n.title}
                      </span>
                      {n.servicos.length > 0 && (
                        <span className="text-certik-muted text-[10px] shrink-0">
                          {n.servicos.length} services
                        </span>
                      )}
                    </div>
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
