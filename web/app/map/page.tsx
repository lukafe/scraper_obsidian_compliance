import { loadJurisdictions } from "@/lib/data";
import { Card } from "@/components/ui/card";
import { WorldMap } from "@/components/charts/world-map";

export default function MapPage() {
  const data = loadJurisdictions();
  return (
    <div className="space-y-6">
      <header className="border-b border-certik-border pb-6">
        <h1 className="text-3xl font-semibold text-white tracking-tight">World map</h1>
        <p className="text-certik-muted mt-2 max-w-3xl leading-relaxed">
          Pick a metric to colour jurisdictions. Hover for the country snapshot. Drag to pan, scroll
          to zoom.
        </p>
      </header>
      <Card>
        <WorldMap data={data} />
      </Card>

      <Card title="Region breakdown">
        <RegionTable data={data} />
      </Card>
    </div>
  );
}

function RegionTable({ data }: { data: ReturnType<typeof loadJurisdictions> }) {
  const groups = new Map<string, typeof data>();
  for (const j of data) {
    const k = j.regiao || "—";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(j);
  }
  const rows = Array.from(groups.entries()).map(([reg, js]) => ({
    reg,
    n: js.length,
    avgServices: js.reduce((a, b) => a + b.n_servicos, 0) / js.length,
    totalNorms: js.reduce((a, b) => a + b.n_normas_total, 0),
  })).sort((a, b) => b.n - a.n);
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-certik-muted border-b border-certik-border">
          <th className="py-2 px-3 font-medium">Region</th>
          <th className="py-2 px-3 text-right font-medium">Jurisdictions</th>
          <th className="py-2 px-3 text-right font-medium">Avg services per jurisdiction</th>
          <th className="py-2 px-3 text-right font-medium">Total norms</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.reg} className="border-b border-certik-border/40">
            <td className="py-2 px-3 text-white">{r.reg}</td>
            <td className="py-2 px-3 text-right">{r.n}</td>
            <td className="py-2 px-3 text-right">{r.avgServices.toFixed(1)}</td>
            <td className="py-2 px-3 text-right">{r.totalNorms}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
