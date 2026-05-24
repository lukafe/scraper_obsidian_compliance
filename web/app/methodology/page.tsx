import { Card } from "@/components/ui/card";
import { loadJurisdictions, loadNorms, loadGraph } from "@/lib/data";

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
      <header>
        <h1 className="text-3xl font-bold text-white">Methodology</h1>
        <p className="text-certik-muted mt-1">
          How the data is built, what the scores mean, and where it's weak.
        </p>
      </header>

      <Card title="Pipeline">
        <ol className="list-decimal pl-5 space-y-2 text-sm text-zinc-300">
          <li><b>Discovery</b> — Gemini 2.5 Flash + Google Search seeded each country from a curated regulatory matrix.</li>
          <li><b>Scrape</b> — official gazettes, regulator portals (Planalto, BaFin, Légifrance, MAS, etc.); Wayback fallback when Cloudflare/WAF blocks.</li>
          <li><b>Translate</b> — auto-translation to English when source isn't English; original preserved alongside.</li>
          <li><b>Analyze</b> — Gemini 2.5 Pro extracts <code className="bg-certik-border/30 px-1 rounded">regime</code>, <code>status_regulatorio</code>, <code>deadline_principal</code>, 7 boolean <code>exige_*</code> triggers, and free-text <code>escopo</code> + <code>gap_ou_ambiguidade</code>.</li>
          <li><b>Aggregate</b> — per-country overview built from underlying norms (any-true on triggers, earliest non-past deadline, top-cited frameworks).</li>
          <li><b>Export</b> — flat CSV + typed graph JSON consumed by this dashboard.</li>
        </ol>
      </Card>

      <Card title="Opportunity Score (0–100)">
        <p className="text-sm text-zinc-300">
          A composite ranking — <span className="text-certik-red">not</span> a final decision, just a quick lens.
        </p>
        <ul className="mt-3 text-sm text-zinc-300 space-y-1">
          <li>• <b>40% Urgency</b> — days to next regulatory deadline (closer = higher; null = neutral 20)</li>
          <li>• <b>40% Service Intensity</b> — # of CertiK services triggered (0–14)</li>
          <li>• <b>20% Maturity</b> — heuristic: # of analyzed norms × # regulators × age of anchor</li>
        </ul>
        <p className="mt-3 text-xs text-certik-muted">
          Weights are tunable in <code>web/lib/scoring.ts</code>. Open a PR if you want to change them.
        </p>
      </Card>

      <Card title="Confidence policy">
        <p className="text-sm text-zinc-300">
          Each LLM-extracted field is tagged with <code>confianca_dados</code> (alta/media/baixa).
          Default after auto-extraction is <b>media</b>. Manual review can elevate to alta.
          Null values are preferred to guesses — so a missing <code>regime</code> means
          "the model wasn't confident", not "no regime exists".
        </p>
        <p className="mt-3 text-sm text-amber-400/80">
          ⚠ The model is deliberately conservative. <code>regime</code> succeeded on ~40% of
          analyzed norms, <code>deadline_principal</code> on ~20%. A future enrichment pass can lift those numbers.
        </p>
      </Card>

      <Card title="Data snapshot">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <div className="text-certik-muted text-xs">Jurisdictions</div>
            <div className="text-2xl text-white">{juris.length}</div>
          </div>
          <div>
            <div className="text-certik-muted text-xs">Norms</div>
            <div className="text-2xl text-white">{norms.length}</div>
          </div>
          <div>
            <div className="text-certik-muted text-xs">Graph nodes</div>
            <div className="text-2xl text-white">{graph.nodes.length}</div>
          </div>
          <div>
            <div className="text-certik-muted text-xs">Graph edges</div>
            <div className="text-2xl text-white">{graph.edges.length}</div>
          </div>
        </div>

        <h4 className="mt-5 text-sm font-semibold text-white">Edge type distribution</h4>
        <ul className="mt-2 grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
          {Array.from(edgeTypes.entries()).sort((a, b) => b[1] - a[1]).map(([t, n]) => (
            <li key={t} className="bg-certik-border/30 rounded px-2 py-1">
              <span className="text-certik-red">{n}</span>{" "}
              <span className="text-zinc-300">{t}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Known limitations">
        <ul className="list-disc pl-5 text-sm text-zinc-300 space-y-1">
          <li>2 jurisdictions (<code>IN</code>, <code>SE</code>) have only stub norms — needed analysis returned no signals.</li>
          <li><code>competidores_ativos</code> and <code>forca_relacionamento_certik</code> are intentionally empty — they require human input from BD.</li>
          <li>Some federal sites with WAF (Legifrance, legislation.gov.uk, uaelegislation.gov.ae) required Wayback fallback; content may be slightly stale.</li>
          <li>The opportunity score is a heuristic — high score doesn't equal a sale, just a candidate to investigate.</li>
        </ul>
      </Card>
    </div>
  );
}
