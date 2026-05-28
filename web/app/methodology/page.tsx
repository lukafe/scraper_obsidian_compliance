import { Card } from "@/components/ui/card";
import { loadJurisdictions, loadNorms, loadGraph } from "@/lib/data";
import { label } from "@/lib/labels";

export default function MethodologyPage() {
  const juris = loadJurisdictions();
  const norms = loadNorms();
  const graph = loadGraph();

  // Stats computed at build time from the actual export.
  const totalEdges = graph.edges.length;
  const edgesByType = new Map<string, number>();
  for (const e of graph.edges) {
    edgesByType.set(e.tipo_relacao, (edgesByType.get(e.tipo_relacao) ?? 0) + 1);
  }

  // Top anchors by total inbound edges (the most-cited norms).
  const inlinks = new Map<string, number>();
  for (const e of graph.edges) {
    inlinks.set(e.target, (inlinks.get(e.target) ?? 0) + 1);
  }
  const idToLabel = new Map(graph.nodes.map((n) => [n.id, n.label]));
  const topAnchors = Array.from(inlinks.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([id, n]) => ({
      id,
      n,
      label: idToLabel.get(id) ?? id,
    }));

  // Binding inheritance — derivado_de targets (which anchors are transposed by the most jurisdictions).
  const derivCount = new Map<string, number>();
  for (const e of graph.edges) {
    if (e.tipo_relacao === "derivado_de") {
      derivCount.set(e.target, (derivCount.get(e.target) ?? 0) + 1);
    }
  }
  const topDerived = Array.from(derivCount.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  // Soft influence — inspirado_em targets.
  const inspCount = new Map<string, number>();
  for (const e of graph.edges) {
    if (e.tipo_relacao === "inspirado_em") {
      inspCount.set(e.target, (inspCount.get(e.target) ?? 0) + 1);
    }
  }
  const topInspired = Array.from(inspCount.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  const nAnalyzed = juris.reduce((acc, j) => acc + j.n_normas_analyzed, 0);
  const nWithDeadline = juris.filter(
    (j) => j.urgencia_deadline_dias !== null,
  ).length;
  const nHighConfidence = juris.filter(
    (j) => j.data_confidence?.tier === "high",
  ).length;

  return (
    <div className="space-y-6">
      <header className="border-b border-certik-border pb-6">
        <h1 className="text-3xl font-semibold text-white tracking-tight">
          How this dashboard works
        </h1>
        <p className="text-certik-muted mt-2 max-w-3xl leading-relaxed">
          From raw legal text to the opportunity score, in plain English. Every number
          shown anywhere in this dashboard is traceable back through the steps below.
        </p>
      </header>

      <Card>
        {/* ---------- Section 1: The pipeline ---------- */}
        <Section
          number="1"
          title="From official text to structured data"
          lead="Five stages, each idempotent and reproducible."
        >
          <ol className="space-y-3 text-sm text-zinc-300 leading-relaxed">
            <Step n={1} title="Discovery">
              A curated regulatory matrix per jurisdiction is fed to a large language
              model with live web-search grounding, which identifies the statutes,
              regulations, circulars and guidance notes worth tracking. Output:{" "}
              <strong>{norms.length.toLocaleString()} candidate norms</strong> across{" "}
              <strong>{juris.length} jurisdictions</strong>.
            </Step>
            <Step n={2} title="Scrape">
              Each norm is fetched from the official source (national gazettes,
              regulator portals, statutory databases). When a primary source is
              unreachable — strict firewalls, login walls, JavaScript-rendered single
              pages — the pipeline falls back to archive snapshots or to a headless
              browser, with the chosen path logged per norm.
            </Step>
            <Step n={3} title="Translate">
              Non-English texts are auto-translated; the original language is preserved
              alongside so legal verification can quote either side.
            </Step>
            <Step n={4} title="Analyse">
              A reasoning LLM reads each body and extracts thirteen structured signals:{" "}
              <code>regime</code>, <code>status_regulatorio</code>, principal deadline
              + deadline type, seven <code>exige_*</code> service triggers (audit,
              proof-of-reserves, pentest, AML/KYT, custody, formal verification,
              independent certification), free-text <code>escopo</code>, and{" "}
              <code>gap_ou_ambiguidade</code>. A second deterministic pass — pure
              algorithm, no LLM — then re-validates every claim: substring presence of
              the quote in the body, imperative-verb test for triggers, temporal-anchor
              test for deadlines, regime-vocabulary test for regimes. Anything that
              fails the validator is stripped back to null.{" "}
              <strong>Phase 1 rule:</strong> every non-null value MUST come with a
              verbatim quote copied from the body. Better silence than a fabricated
              claim.
            </Step>
            <Step n={5} title="Aggregate &amp; export">
              Per-country overviews are built from the underlying norms. Any-true on
              triggers, earliest non-past deadline, six text-grounded coverage dimensions
              (issuance / custody / market abuse / AML / taxation / consumer protection)
              that drive the maturity tag. A flat CSV plus a typed graph JSON are
              exported and consumed by this dashboard.
            </Step>
          </ol>

          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <KeyStat
              top="Jurisdictions"
              big={juris.length.toString()}
              bottom="tracked end-to-end"
            />
            <KeyStat
              top="Norms"
              big={norms.length.toLocaleString()}
              bottom={`${nAnalyzed.toLocaleString()} fully analysed`}
            />
            <KeyStat
              top="Verified deadlines"
              big={nWithDeadline.toString()}
              bottom="body-grounded only"
            />
            <KeyStat
              top="High-confidence markets"
              big={nHighConfidence.toString()}
              bottom="of 23, after Phase 1 rerun"
            />
          </div>
        </Section>

        <Divider />

        {/* ---------- Section 2: Typed relations ---------- */}
        <Section
          number="2"
          title="How norms connect across borders"
          lead="A regulatory text never lives alone. The graph captures nine ways one norm can relate to another."
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <RelationBlock
              colour="#E83C32"
              title="Binding inheritance"
              code="derivado_de"
              description="The source norm legally transposes the target. Created when the body cites the anchor by ID AND, after the Phase 1 rerun, when transposition verbs (“transposes”, “implementa”, “umsetzt”) appear in an evidence quote."
              count={edgesByType.get("derivado_de") ?? 0}
            />
            <RelationBlock
              colour="#FFB300"
              title="Soft inspiration"
              code="inspirado_em"
              description="The source norm aligns with the target without being legally bound to it. Captures non-EU jurisdictions referencing MiCA, every jurisdiction referencing the FATF Recommendations, and similar."
              count={edgesByType.get("inspirado_em") ?? 0}
            />
            <RelationBlock
              colour="#888"
              title="Cross-reference"
              code="referencia_cruzada"
              description="An explicit citation between two norms in the corpus, surfaced from the body text."
              count={edgesByType.get("referencia_cruzada") ?? 0}
            />
            <RelationBlock
              colour="#9C27B0"
              title="Applies to"
              code="aplica_se_a"
              description="A jurisdiction-level overview pointing to its framework anchors."
              count={edgesByType.get("aplica_se_a") ?? 0}
            />
            <RelationBlock
              colour="#4CAF50"
              title="Triggers service"
              code="exige_servico"
              description="A norm requires a CertiK service offering. Driven by the seven boolean exige_* triggers."
              count={edgesByType.get("exige_servico") ?? 0}
            />
            <RelationBlock
              colour="#666"
              title="Citation / Semantic"
              code="citation / semantic"
              description="Background relations: literal citations found in the body and model-suggested similarity. Lower signal — toggle off in the graph view to focus on binding and soft inheritance."
              count={
                (edgesByType.get("citation") ?? 0) +
                (edgesByType.get("semantic") ?? 0)
              }
            />
          </div>

          <p className="text-xs text-certik-muted mt-4">
            Total edges: <strong>{totalEdges.toLocaleString()}</strong> across nine
            typed relations. See <code>src/typed_relations.py</code> for the derivation
            rules.
          </p>
        </Section>

        <Divider />

        {/* ---------- Section 3: The big patterns ---------- */}
        <Section
          number="3"
          title="What the graph already reveals"
          lead="The strongest signal in the dataset is which texts everyone else copies — and which only Europe copies."
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-semibold text-white mb-2">
                Universal anchors
              </h4>
              <p className="text-xs text-certik-muted mb-3 leading-relaxed">
                Norms cited by the largest number of other norms across the entire
                corpus. The FATF Recommendations dominate — every jurisdiction tracked
                follows them — and the EU's MiCA is the binding spine of the European
                cluster.
              </p>
              <ol className="space-y-1.5 text-xs">
                {topAnchors.map((a, i) => (
                  <li
                    key={a.id}
                    className="grid grid-cols-12 items-center gap-2 px-2 py-1 rounded hover:bg-certik-border/20"
                  >
                    <span className="col-span-1 text-certik-muted">{i + 1}</span>
                    <span className="col-span-7 truncate">
                      <span className="text-certik-red font-mono text-[11px]">
                        {a.id}
                      </span>
                      <span className="text-zinc-400 text-[11px] block truncate">
                        {a.label}
                      </span>
                    </span>
                    <span className="col-span-4 text-right font-mono text-white">
                      {a.n}
                      <span className="text-certik-muted text-[11px] ml-1">
                        inlinks
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-white mb-2">
                Binding transposition — only Europe goes here
              </h4>
              <p className="text-xs text-certik-muted mb-3 leading-relaxed">
                The <code>derivado_de</code> relation requires legal transposition.
                Today every binding transposition is a European national text rewriting
                an EU regulation; non-EU jurisdictions use soft alignment instead.
              </p>
              <ul className="space-y-1.5 text-xs">
                {topDerived.map(([target, n]) => (
                  <li
                    key={target}
                    className="flex justify-between bg-certik-border/20 rounded px-2 py-1.5"
                  >
                    <span>
                      <span className="text-certik-red font-mono text-[11px]">
                        {target}
                      </span>
                      <span className="text-zinc-400 text-[11px] block">
                        {idToLabel.get(target)?.slice(0, 60) ?? ""}
                      </span>
                    </span>
                    <span className="font-mono text-white text-right shrink-0 ml-2">
                      {n}
                      <span className="text-certik-muted text-[11px] ml-1">
                        nat. laws
                      </span>
                    </span>
                  </li>
                ))}
              </ul>

              <h4 className="text-sm font-semibold text-white mt-5 mb-2">
                Soft influence — where the world looks
              </h4>
              <p className="text-xs text-certik-muted mb-3 leading-relaxed">
                The <code>inspirado_em</code> relation: non-binding alignment. FATF
                covers everyone; MiCA's soft reach extends well beyond the EEA.
              </p>
              <ul className="space-y-1.5 text-xs">
                {topInspired.map(([target, n]) => (
                  <li
                    key={target}
                    className="flex justify-between bg-certik-border/20 rounded px-2 py-1.5"
                  >
                    <span>
                      <span className="text-amber-400 font-mono text-[11px]">
                        {target}
                      </span>
                      <span className="text-zinc-400 text-[11px] block">
                        {idToLabel.get(target)?.slice(0, 60) ?? ""}
                      </span>
                    </span>
                    <span className="font-mono text-white text-right shrink-0 ml-2">
                      {n}
                      <span className="text-certik-muted text-[11px] ml-1">
                        followers
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Section>

        <Divider />

        {/* ---------- Section 4: Coverage + maturity ---------- */}
        <Section
          number="4"
          title="What makes a market mature"
          lead="Maturity is not a structural heuristic. It's the count of regulatory dimensions actually addressed in the source text."
        >
          <p className="text-sm text-zinc-300 leading-relaxed">
            Six dimensions form the spine of a comprehensive crypto framework: token
            issuance, custody of client assets, market abuse, AML / KYT / Travel Rule,
            taxation, and consumer protection. For every analysed norm we detect which
            dimensions it touches — via boolean triggers plus a multilingual
            word-boundary keyword scan. A jurisdiction's maturity then ranks the union
            of dimensions across all its norms.
          </p>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <MaturityTier
              label="High"
              hint="5+ of 6 dimensions"
              colour="text-emerald-400"
              border="border-emerald-600/40"
              bg="bg-emerald-900/15"
            />
            <MaturityTier
              label="Medium"
              hint="3-4 of 6 dimensions"
              colour="text-amber-400"
              border="border-amber-600/40"
              bg="bg-amber-900/15"
            />
            <MaturityTier
              label="Low"
              hint="1-2 of 6 dimensions"
              colour="text-zinc-300"
              border="border-zinc-600/40"
              bg="bg-zinc-800/30"
            />
          </div>
          <p className="text-xs text-certik-muted mt-3">
            The previous 40-norms / 3-regulators / anchor-before-2020 heuristic is
            removed; see <code>src/coverage.py</code>.
          </p>
        </Section>

        <Divider />

        {/* ---------- Section 5: Opportunity score ---------- */}
        <Section
          number="5"
          title="The opportunity score"
          lead="A composite of urgency, service intensity, and maturity. Tunable in one file."
        >
          <ul className="space-y-1.5 text-sm text-zinc-300">
            <li>
              <span className="text-white font-medium">40% Urgency.</span> Days to the
              next regulatory deadline. Past-due decays from 100 toward a 50 floor over
              12 months. Missing deadline + known regime = 30. Missing deadline +
              unknown regime = 0.
            </li>
            <li>
              <span className="text-white font-medium">40% Service intensity.</span>{" "}
              Share of the 14 CertiK services triggered (audit, pentest, AML/KYT,
              proof of reserves, …).
            </li>
            <li>
              <span className="text-white font-medium">20% Market maturity.</span> The
              text-grounded six-dimension count from section 4.
            </li>
          </ul>
          <p className="text-xs text-certik-muted mt-3">
            Formula in <code>web/lib/scoring.ts</code>. Weight sensitivity has been
            swept; nine jurisdictions stay top-12 under every combination — see the
            calibration note below.
          </p>
        </Section>

        <Divider />

        {/* ---------- Section 6: Deadline policy ---------- */}
        <Section
          number="6"
          title="Deadline policy"
          lead="A deadline is shown only when it can be quoted from the source text."
        >
          <p className="text-sm text-zinc-300 leading-relaxed">
            A retroactive audit (
            <code>scripts/audit_deadlines.py</code>) confirmed only 16 of 83 norm-level
            deadlines had body grounding; the remaining 67 — many of them publication
            dates, founding years or inferred end-of-period markers wrongly flagged as
            deadlines — were removed from the vault. After the Phase 1 rerun, deadlines
            re-appear if and only if the body quotes the date next to a temporal anchor
            ("by", "before", "até", "spätestens", "deadline", "in force") within 80
            characters.
          </p>
        </Section>

        <Divider />

        {/* ---------- Section 7: Confidence ---------- */}
        <Section
          number="7"
          title="How much to trust each number"
          lead="A separate orthogonal score, never used to gate the ranking — it sits next to it so the decision-maker can see what the data is built on."
        >
          <p className="text-sm text-zinc-300 leading-relaxed">
            For every jurisdiction we publish a 0-100 data-confidence score and a
            tier badge. Four orthogonal components: how much of the country's corpus is
            LLM-analysed (35%), how many of the six dimensions are covered (25%), how
            many distinct regulators contribute (15%), and the share of extracted
            fields backed by a Phase 1 verbatim quote (25%). The badge shown on the home
            table, the country profile and the recommended-moves cards reflects this score.
          </p>
        </Section>

        <Divider />

        {/* ---------- Section 8: Calibration ---------- */}
        <Section
          number="8"
          title="Calibration — gold set + F1 + drift gate"
          lead="Every change to the extraction logic is measured against a hand-labelled ground truth."
        >
          <p className="text-sm text-zinc-300 leading-relaxed">
            The gold set is a stratified sample seeded with the current extraction; a
            human reviewer corrects each field and pastes a verbatim source quote, then
            flips <code>reviewed: true</code>. The comparator (
            <code>scripts/gold.py report</code>) reports per-field precision, recall
            and F1 against a saved baseline. CI fails any PR that drops a field by
            more than 5 percentage points.
          </p>
          <p className="text-sm text-amber-300/90 leading-relaxed mt-3">
            Current measurement on a 13-row starter pack: support-weighted F1 ={" "}
            <strong>0.80</strong>. The model is perfect on{" "}
            <code>exige_certificacao_independente</code> and <code>escopo</code> (1.00)
            and strong on <code>regime</code> (0.91). The two structural weaknesses
            are unchanged after the Phase 1 rerun: a bias toward TRUE on{" "}
            <code>exige_seguranca_custodia</code> (0.36) and <code>exige_kyt_aml</code>{" "}
            (0.50), where the source body uses descriptive prose rather than the
            imperative verbs the validator demands. Net effect for the decision-maker:
            those two triggers should be cross-checked manually before any commercial
            move; the other eleven fields are reliable.
          </p>
        </Section>

        <Divider />

        {/* ---------- Section 9: Limits ---------- */}
        <Section
          number="9"
          title="Honest limits"
          lead="What this dashboard is NOT."
        >
          <ul className="list-disc pl-5 text-sm text-zinc-300 space-y-1.5 leading-relaxed">
            <li>
              Two jurisdictions (<code>IN</code>, <code>SE</code>) have only stub norms
              — the analysis pass returned no usable signals. They are shown for
              completeness, not for ranking.
            </li>
            <li>
              <code>competidores_ativos</code> and{" "}
              <code>forca_relacionamento_certik</code> are intentionally empty — they
              require business-development input that the LLM cannot infer from public
              text.
            </li>
            <li>
              A handful of national gazettes are behind aggressive firewalls and were
              fetched from official archive snapshots; their content can be slightly
              stale until the next refresh cycle.
            </li>
            <li>
              The opportunity score is a heuristic — a high score is a candidate to
              investigate, not a closed sale.
            </li>
          </ul>
        </Section>
      </Card>
    </div>
  );
}

/* ---------- Helpers ---------- */

function Section({
  number,
  title,
  lead,
  children,
}: {
  number: string;
  title: string;
  lead: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <header className="flex items-start gap-3 mb-3">
        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-certik-red/20 text-certik-red font-mono text-sm font-semibold shrink-0">
          {number}
        </span>
        <div>
          <h2 className="text-base font-semibold text-white">{title}</h2>
          <p className="text-xs text-certik-muted mt-0.5">{lead}</p>
        </div>
      </header>
      <div className="pl-10">{children}</div>
    </section>
  );
}

function Divider() {
  return <hr className="my-6 border-certik-border/60" />;
}

function Step({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex gap-3">
      <span className="font-mono text-certik-muted text-xs mt-0.5 w-6 shrink-0">
        {String(n).padStart(2, "0")}
      </span>
      <div>
        <span className="text-white font-medium">{title}.</span>{" "}
        <span className="text-zinc-300">{children}</span>
      </div>
    </li>
  );
}

function KeyStat({ top, big, bottom }: { top: string; big: string; bottom: string }) {
  return (
    <div className="bg-certik-border/15 rounded-lg p-3 border border-certik-border/40">
      <div className="text-[10px] uppercase tracking-wider text-certik-muted">
        {top}
      </div>
      <div className="text-2xl text-white font-semibold mt-1 font-mono">{big}</div>
      <div className="text-[11px] text-zinc-400 mt-1 leading-snug">{bottom}</div>
    </div>
  );
}

function RelationBlock({
  colour,
  title,
  code,
  description,
  count,
}: {
  colour: string;
  title: string;
  code: string;
  description: string;
  count: number;
}) {
  return (
    <div className="border border-certik-border/60 rounded p-3 flex gap-3">
      <span
        className="inline-block w-1 rounded-full shrink-0"
        style={{ background: colour }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <h4 className="text-sm font-semibold text-white">{title}</h4>
          <span className="text-xs font-mono text-certik-muted">
            {count.toLocaleString()} edges
          </span>
        </div>
        <div className="text-[11px] font-mono text-certik-muted mt-0.5">{code}</div>
        <p className="text-xs text-zinc-300 mt-2 leading-relaxed">{description}</p>
      </div>
    </div>
  );
}

function MaturityTier({
  label: tierLabel,
  hint,
  colour,
  border,
  bg,
}: {
  label: string;
  hint: string;
  colour: string;
  border: string;
  bg: string;
}) {
  return (
    <div className={`rounded-lg border p-3 ${border} ${bg}`}>
      <div className={`text-base font-semibold ${colour}`}>{tierLabel}</div>
      <div className="text-xs text-zinc-300 mt-1">{hint}</div>
    </div>
  );
}
