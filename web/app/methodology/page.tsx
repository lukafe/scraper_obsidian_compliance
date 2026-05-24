import { Card } from "@/components/ui/card";
import { loadJurisdictions, loadNorms, loadGraph } from "@/lib/data";
import { label } from "@/lib/labels";

export default function MethodologyPage() {
  const juris = loadJurisdictions();
  const norms = loadNorms();
  const graph = loadGraph();
  const edgeTypes = new Map<string, number>();
  for (const e of graph.edges) {
    edgeTypes.set(e.tipo_relacao, (edgeTypes.get(e.tipo_relacao) ?? 0) + 1);
  }
  return (
    <div className="space-y-6">
      <header className="border-b border-certik-border pb-6">
        <h1 className="text-3xl font-semibold text-white tracking-tight">Methodology</h1>
        <p className="text-certik-muted mt-2 max-w-3xl leading-relaxed">
          How the underlying data is built, what each score means, and where the model is weak.
        </p>
      </header>

      <Card title="Pipeline">
        <ol className="list-decimal pl-5 space-y-2 text-sm text-zinc-300 leading-relaxed">
          <li>
            <span className="text-white font-medium">Discovery.</span> Gemini 2.5 Flash with Google
            Search seeded each country from a curated regulatory matrix.
          </li>
          <li>
            <span className="text-white font-medium">Scrape.</span> Official gazettes and regulator
            portals (Planalto, BaFin, Légifrance, MAS and equivalents). When a Web Application
            Firewall blocks direct access, the pipeline falls back to the Wayback Machine.
          </li>
          <li>
            <span className="text-white font-medium">Translate.</span> Sources are auto-translated
            to English when needed; the original text is preserved alongside.
          </li>
          <li>
            <span className="text-white font-medium">Analyse.</span> Gemini 2.5 Pro extracts the
            regulatory regime, status, principal deadline, seven boolean service triggers, and free
            text for scope and gaps or ambiguities.
          </li>
          <li>
            <span className="text-white font-medium">Aggregate.</span> Per-country overviews are
            built from the underlying norms (any-true on triggers, earliest non-past deadline, top
            cited frameworks).
          </li>
          <li>
            <span className="text-white font-medium">Export.</span> A flat CSV plus a typed graph
            JSON are consumed by this dashboard.
          </li>
        </ol>
      </Card>

      <Card title="Opportunity score (0 to 100)">
        <p className="text-sm text-zinc-300 leading-relaxed">
          A composite ranking — not a final decision, simply a quick lens to surface candidates.
        </p>
        <ul className="mt-3 text-sm text-zinc-300 space-y-1.5">
          <li>
            <span className="text-white font-medium">40% Urgency.</span> Days to the next
            regulatory deadline. Past-due deadlines decay from 100 toward a 50 floor over
            12 months (the sales window closes as the rule beds in). A missing deadline
            scores 30 when the regime is known and 0 when it is unknown — silence with no
            structural context is not a buying signal.
          </li>
          <li>
            <span className="text-white font-medium">40% Service intensity.</span> Number of
            CertiK services triggered (0 to 14).
          </li>
          <li>
            <span className="text-white font-medium">20% Market maturity.</span> Now grounded
            in the underlying text: a 0-to-6 count of the regulatory dimensions the
            jurisdiction's norms actually cover (issuance, custody, market abuse, AML,
            taxation, consumer protection). High maturity requires 5+ dimensions, medium
            3-4, low 1-2. The previous 40-norms / 3-regulators / anchor-before-2020
            heuristic has been removed.
          </li>
        </ul>
        <p className="mt-3 text-xs text-certik-muted">
          Weights are tunable in <code>web/lib/scoring.ts</code>; coverage detection is in
          <code> src/coverage.py</code>.
        </p>
      </Card>

      <Card title="Confidence policy">
        <p className="text-sm text-zinc-300 leading-relaxed">
          Each extracted field carries a confidence tag (High, Medium, or Low). The default after
          auto-extraction is Medium; manual review can elevate to High. Null values are preferred
          over guesses — a missing regime means the model was not confident, not that no regime
          exists.
        </p>
        <p className="mt-3 text-sm text-amber-300/90 leading-relaxed">
          The model is deliberately conservative. The regime field was extracted on approximately
          40% of analysed norms; the principal deadline on approximately 20%. A future enrichment
          pass can lift those figures.
        </p>
      </Card>

      <Card title="Data snapshot">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <div className="text-certik-muted text-xs uppercase tracking-wide">Jurisdictions</div>
            <div className="text-2xl text-white mt-1">{juris.length}</div>
          </div>
          <div>
            <div className="text-certik-muted text-xs uppercase tracking-wide">Norms</div>
            <div className="text-2xl text-white mt-1">{norms.length}</div>
          </div>
          <div>
            <div className="text-certik-muted text-xs uppercase tracking-wide">Graph nodes</div>
            <div className="text-2xl text-white mt-1">{graph.nodes.length}</div>
          </div>
          <div>
            <div className="text-certik-muted text-xs uppercase tracking-wide">Graph edges</div>
            <div className="text-2xl text-white mt-1">{graph.edges.length}</div>
          </div>
        </div>

        <h4 className="mt-6 text-sm font-semibold text-white">Edge-type distribution</h4>
        <ul className="mt-2 grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
          {Array.from(edgeTypes.entries()).sort((a, b) => b[1] - a[1]).map(([t, n]) => (
            <li key={t} className="bg-certik-border/30 rounded px-2 py-1">
              <span className="text-certik-red font-mono">{n}</span>{" "}
              <span className="text-zinc-300">{label.edgeType(t)}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Known limitations">
        <ul className="list-disc pl-5 text-sm text-zinc-300 space-y-1.5 leading-relaxed">
          <li>
            Two jurisdictions (India and Sweden) currently have only stub norms — the analysis pass
            returned no usable signals.
          </li>
          <li>
            Active-competitor presence and CertiK relationship strength are intentionally empty;
            they require human input from the business-development team.
          </li>
          <li>
            Some federal sites with strict firewalls (Légifrance, legislation.gov.uk, parts of
            uaelegislation.gov.ae) required the Wayback fallback; content may be slightly stale.
          </li>
          <li>
            The opportunity score is a heuristic — a high score is a candidate to investigate, not
            a closed sale.
          </li>
        </ul>
      </Card>
    </div>
  );
}
