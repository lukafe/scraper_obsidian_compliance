import { loadJurisdictions, loadNorms, loadGraph } from "@/lib/data";
import { opportunityScore, urgencyColor, maturityColor } from "@/lib/scoring";
import { Card, Kpi } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SERVICE_CATEGORIES, SERVICE_LABELS } from "@/lib/types";
import { label } from "@/lib/labels";
import Link from "next/link";
import { notFound } from "next/navigation";

interface Props {
  params: Promise<{ iso: string }>;
}

export async function generateStaticParams() {
  return loadJurisdictions().map((j) => ({ iso: j.iso }));
}

export default async function JurisdictionPage({ params }: Props) {
  const { iso: rawIso } = await params;
  const iso = rawIso.toUpperCase();
  const juris = loadJurisdictions().find((j) => j.iso === iso);
  if (!juris) return notFound();

  const score = opportunityScore(juris);
  const norms = loadNorms().filter((n) => n.country === iso && !n.in_quarantine);
  const graph = loadGraph();

  // Build category → services-triggered counts
  const servicesByCat = Object.entries(SERVICE_CATEGORIES).map(([cat, services]) => ({
    cat,
    services: services.map((s) => ({
      key: s, label: SERVICE_LABELS[s] ?? s,
      triggered: juris.servicos.includes(s),
      n_norms: norms.filter((n) => n.servicos.includes(s)).length,
    })),
  }));

  // Edges from/to this jurisdiction node + its norm nodes
  const myIds = new Set([iso, ...norms.map((n) => n.id)]);
  const edges = graph.edges.filter((e) => myIds.has(e.source));
  const derivado = edges.filter((e) => e.tipo_relacao === "derivado_de");
  const inspirado = edges.filter((e) => e.tipo_relacao === "inspirado_em");
  const refs = edges.filter((e) => e.tipo_relacao === "referencia_cruzada");

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between flex-wrap gap-2">
        <div>
          <Link href="/jurisdictions" className="text-xs text-certik-muted hover:text-certik-red">
            ← all jurisdictions
          </Link>
          <h1 className="text-3xl font-bold text-white">
            {juris.pais} <span className="text-certik-muted text-2xl">({iso})</span>
          </h1>
          <p className="text-certik-muted mt-0.5">
            {juris.regiao} · Lead regulator: <span className="text-white">{juris.regulador_principal ?? "—"}</span>
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs text-certik-muted">Opportunity Score</div>
          <div
            className="px-4 py-2 rounded font-mono text-xl mt-1"
            style={{
              background: `rgba(232,60,50,${score / 100})`,
              color: score > 60 ? "white" : "#FCC",
            }}
          >
            {score.toFixed(1)}
          </div>
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Kpi label="Norms tracked" value={juris.n_normas_total} />
        <Kpi label="LLM-analyzed" value={juris.n_normas_analyzed} hint={`${(juris.n_normas_analyzed / Math.max(1, juris.n_normas_total) * 100).toFixed(0)}% coverage`} />
        <Kpi label="CertiK services" value={`${juris.n_servicos}/14`} accent />
        <Kpi
          label="Maturity"
          value={
            <span style={{ color: maturityColor(juris.maturidade_mercado) }}>
              {label.maturity(juris.maturidade_mercado)}
            </span>
          }
        />
        <Kpi
          label="Next deadline"
          value={juris.deadline_principal ?? "—"}
          hint={juris.urgencia_deadline_dias !== null ? `${juris.urgencia_deadline_dias} days` : undefined}
        />
      </div>

      {juris.reguladores_secundarios.length > 0 && (
        <Card title="Regulators">
          <div className="flex flex-wrap gap-2">
            <Badge variant="red">{juris.regulador_principal} (lead)</Badge>
            {juris.reguladores_secundarios.map((r) => (
              <Badge key={r} variant="default">{r}</Badge>
            ))}
          </div>
        </Card>
      )}

      <Card title="CertiK services triggered" subtitle="Green = triggered by at least one norm in this jurisdiction.">
        <div className="space-y-5">
          {servicesByCat.map(({ cat, services }) => (
            <div key={cat}>
              <h4 className="text-sm font-semibold text-white mb-2">{cat}</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {services.map((s) => (
                  <div
                    key={s.key}
                    className={`px-3 py-2 rounded border text-xs flex items-center justify-between ${
                      s.triggered
                        ? "border-certik-red/50 bg-certik-red/10"
                        : "border-certik-border bg-certik-panel"
                    }`}
                  >
                    <span className={s.triggered ? "text-white" : "text-certik-muted"}>
                      {s.label}
                    </span>
                    {s.triggered && <span className="text-certik-red font-mono">{s.n_norms}n</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card
        title="Underlying norms"
        subtitle={`${norms.length} norms with regime, scope, gaps and verbatim evidence quotes.`}
      >
        <div className="space-y-3 max-h-[700px] overflow-y-auto">
          {norms.map((n) => {
            const evidenceEntries = Object.entries(n.evidence ?? {}).filter(
              ([, quote]) => !!quote,
            );
            return (
              <article key={n.id} className="border-b border-certik-border/30 pb-3 last:border-0">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-white">{n.title}</div>
                    <div className="text-xs text-certik-muted mt-0.5">
                      {n.type} · {n.regulator ?? "—"} · {n.date ?? "—"}
                    </div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    {n.regime && <Badge variant="red">{label.regime(n.regime)}</Badge>}
                    {n.status_regulatorio && (
                      <Badge variant="amber">{label.status(n.status_regulatorio)}</Badge>
                    )}
                    {n.deadline_principal && (
                      <Badge variant="default" className="font-mono">{n.deadline_principal}</Badge>
                    )}
                  </div>
                </div>
                {n.escopo && (
                  <p className="text-sm text-zinc-300 mt-2">
                    <span className="text-certik-muted">Scope:</span> {n.escopo}
                  </p>
                )}
                {n.gap_ou_ambiguidade && (
                  <p className="text-sm text-amber-200/80 mt-1">
                    <span className="text-amber-400 font-semibold">Gap or ambiguity:</span>{" "}
                    {n.gap_ou_ambiguidade}
                  </p>
                )}
                {n.servicos.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {n.servicos.map((s) => (
                      <Badge key={s} variant="default" className="text-[10px]">
                        {SERVICE_LABELS[s] ?? s}
                      </Badge>
                    ))}
                  </div>
                )}
                {evidenceEntries.length > 0 && (
                  <details className="mt-2 group">
                    <summary className="text-xs text-certik-muted hover:text-certik-red cursor-pointer select-none">
                      Evidence ({evidenceEntries.length}) — verbatim quotes from the source
                    </summary>
                    <ul className="mt-2 space-y-2 pl-3 border-l-2 border-certik-border">
                      {evidenceEntries.map(([field, quote]) => (
                        <li key={field} className="text-xs">
                          <div className="text-certik-muted font-mono text-[10px] uppercase tracking-wide">
                            {humanField(field)}
                          </div>
                          <blockquote className="text-zinc-300 italic mt-0.5">
                            &ldquo;{quote}&rdquo;
                          </blockquote>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {n.source_url && (
                  <a
                    href={n.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-certik-muted hover:text-certik-red mt-2 inline-block"
                  >
                    source ↗
                  </a>
                )}
              </article>
            );
          })}
        </div>
      </Card>

      <Card
        title="Connected frameworks"
        subtitle="How this jurisdiction inherits, is inspired by, or cites other regulatory texts."
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <RelationGroup
            title="Direct implementation"
            description="Binding transposition of a supranational anchor."
            edges={derivado}
          />
          <RelationGroup
            title="Soft inspiration"
            description="Non-binding alignment with standards or foreign law."
            edges={inspirado}
          />
          <RelationGroup
            title="Cross-citations"
            description="Explicit citations in the body of norms."
            edges={refs.slice(0, 30)}
          />
        </div>
      </Card>
    </div>
  );
}

const EVIDENCE_FIELD_LABELS: Record<string, string> = {
  regime: "Regime",
  status_regulatorio: "Status",
  deadline_principal: "Principal deadline",
  tipo_deadline: "Deadline type",
  exige_auditoria_tecnica: "Requires technical audit",
  exige_proof_of_reserves: "Requires proof of reserves",
  exige_pentest: "Requires penetration test",
  exige_kyt_aml: "Requires AML / KYT",
  exige_seguranca_custodia: "Requires custody security",
  exige_formal_verification: "Requires formal verification",
  exige_certificacao_independente: "Requires independent certification",
};

function humanField(field: string): string {
  return EVIDENCE_FIELD_LABELS[field] ?? field;
}

function RelationGroup({ title, description, edges }: {
  title: string; description: string;
  edges: { source: string; target: string; justificativa?: string }[];
}) {
  if (edges.length === 0) {
    return (
      <div>
        <h4 className="text-sm font-semibold text-white">{title}</h4>
        <p className="text-xs text-certik-muted mt-1">{description}</p>
        <p className="text-xs text-certik-muted mt-3 italic">No edges.</p>
      </div>
    );
  }
  // Group by target
  const byTarget = new Map<string, string | undefined>();
  for (const e of edges) {
    if (!byTarget.has(e.target)) byTarget.set(e.target, e.justificativa);
  }
  return (
    <div>
      <h4 className="text-sm font-semibold text-white">{title} <span className="text-certik-muted font-normal">({edges.length})</span></h4>
      <p className="text-xs text-certik-muted mt-1 mb-3">{description}</p>
      <ul className="space-y-1 max-h-72 overflow-y-auto">
        {Array.from(byTarget.entries()).slice(0, 20).map(([target, just]) => (
          <li key={target} className="text-xs">
            <div className="text-certik-red font-mono text-[11px]">{target}</div>
            {just && <div className="text-zinc-400">{just}</div>}
          </li>
        ))}
      </ul>
    </div>
  );
}
