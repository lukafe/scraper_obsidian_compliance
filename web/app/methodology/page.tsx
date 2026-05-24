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

      <Card title="Calibration — gold set">
        <p className="text-sm text-zinc-300 leading-relaxed">
          Every change to the extraction logic, the keyword vocabulary, or the scoring
          formula is now measured against a hand-labelled gold set. The set is a stratified
          sample of 100 norms balanced across region, regulatory regime and trigger density;
          each row is annotated directly from the source legal text with a verbatim evidence
          quote per non-null field.
        </p>
        <p className="text-sm text-zinc-300 leading-relaxed mt-3">
          The comparator (<code>python scripts/gold.py report</code>) reports per-field
          precision, recall and F1, and tracks drift against a saved baseline. A starter
          pack of 5 hand-annotated rows is checked in; the remaining 95 are seeded with the
          current extraction (ready for human review-and-correct rather than write-from-scratch).
        </p>
        <p className="text-sm text-amber-300/90 leading-relaxed mt-3">
          Current measurement on the 13-row starter pack: support-weighted F1 = 0.85. The
          model is perfect on <code>exige_certificacao_independente</code> and
          <code> escopo</code> (F1 = 1.00) and strong on regime detection (F1 = 0.91); it
          has a clear bias toward TRUE on the trigger booleans where the source text is
          ambiguous — <code>exige_seguranca_custodia</code> (F1 = 0.36) and
          <code> exige_kyt_aml</code> (F1 = 0.50) over-claim 6-7 times across the gold
          rows. Status defaults to "vigente" (F1 = 0.56). These over-claim patterns are
          exactly what Phase 1 evidence quotes are designed to strip out — the next
          analyzer pass will demote any TRUE that the LLM cannot quote.
        </p>
      </Card>

      <Card title="Data confidence (Phase 5)">
        <p className="text-sm text-zinc-300 leading-relaxed">
          The opportunity score answers "how attractive?". A separate confidence indicator
          answers "how much should I trust this?". It combines four orthogonal signals,
          weighted to add up to one:
        </p>
        <ul className="mt-3 text-sm text-zinc-300 space-y-1.5">
          <li>
            <span className="text-white font-medium">35% Analysis coverage.</span> Share of
            tracked norms that have been LLM-analyzed.
          </li>
          <li>
            <span className="text-white font-medium">25% Coverage breadth.</span> How many of
            the six regulatory dimensions this jurisdiction's norms address.
          </li>
          <li>
            <span className="text-white font-medium">15% Regulator diversity.</span> A
            saturating curve over the count of distinct regulators contributing norms.
          </li>
          <li>
            <span className="text-white font-medium">25% Evidence density.</span> Share of
            extracted fields backed by a verbatim source quote (Phase 1). Lights up as the
            gap analyzer is rerun.
          </li>
        </ul>
        <p className="mt-3 text-xs text-certik-muted">
          Confidence is shown as a coloured badge next to every country's score; the
          country page expands the four components. It is never used to gate the ranking —
          a low-confidence country can still be a real opportunity, just a noisier one.
        </p>
      </Card>

      <Card title="Weight sensitivity (Phase 5)">
        <p className="text-sm text-zinc-300 leading-relaxed">
          The opportunity score's 40/40/20 weights are operator choices. To surface which
          rankings actually depend on those choices,
          <code> scripts/calibrate.py</code> sweeps every triplet in (0.1 to 0.7) that sums
          to 1.0 — 33 combinations — and counts how often each country lands in the top-12.
        </p>
        <ul className="mt-3 text-sm text-zinc-300 space-y-1.5">
          <li>
            <span className="text-emerald-400 font-medium">Robust (top-12 in all 33 combos):</span>{" "}
            <span className="font-mono">BR, US, DE, IT, HK, SG, GB, AE, AR</span>. Brazil
            holds rank 1 in every single combination — the strongest defensible call.
          </li>
          <li>
            <span className="text-amber-400 font-medium">Weight-sensitive:</span>{" "}
            <span className="font-mono">CA, FR, UY</span> (each appears in ~85-88% of
            combinations), <span className="font-mono">TR</span> (only 39%). Treat these as
            "depends on operator emphasis".
          </li>
          <li>
            <span className="text-certik-muted">Never top-12:</span>{" "}
            <span className="font-mono">BM, CH, IN, JP, KR, LT, MX, NG, SE, ZA</span> — not
            in scope regardless of weight choice.
          </li>
        </ul>
        <p className="mt-3 text-xs text-certik-muted">
          With an expert ranking from BD, the same script can do supervised tuning
          (Pearson against the expert column) and propose the best-correlated weights.
        </p>
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
