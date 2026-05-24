import { Card } from "@/components/ui/card";
import { GraphView } from "@/components/charts/graph-view";
import { loadGraph, loadJurisdictions } from "@/lib/data";

export default function GraphPage() {
  const graph = loadGraph();
  const juris = loadJurisdictions();

  const isoToRegion = Object.fromEntries(juris.map((j) => [j.iso, j.regiao]));

  return (
    <div className="space-y-6">
      <header className="border-b border-certik-border pb-6">
        <h1 className="text-3xl font-semibold text-white tracking-tight">
          Regulatory graph
        </h1>
        <p className="text-certik-muted mt-2 max-w-3xl leading-relaxed">
          Every norm and jurisdiction in the vault, connected by typed relations —
          binding transposition, soft inspiration, cross-references, regulator and
          service ties. Drag to pan, scroll to zoom, click any node for its
          neighbours. Filter by relation type in the right rail.
        </p>
      </header>

      <Card>
        <GraphView graph={graph} isoToRegion={isoToRegion} />
      </Card>

      <Card title="How to read this">
        <ul className="text-sm text-zinc-300 space-y-2 leading-relaxed">
          <li>
            <span className="text-white font-medium">Bordered circles</span> are
            jurisdictions, <span className="text-white font-medium">filled circles</span>{" "}
            are individual norms. Size scales with the number of inlinks — the
            most-cited norms are visibly larger.
          </li>
          <li>
            <span className="text-white font-medium">Region colour</span> applies to
            both jurisdictions and the norms anchored to them. Use the legend on the
            right to read it. Supranational anchors (MiCA, FATF, Basel, etc.) appear in
            red.
          </li>
          <li>
            <span className="text-white font-medium">Relation types</span> can be
            toggled on/off. Hiding <code>citation</code> and <code>semantic</code>{" "}
            clarifies the picture of binding (<code>derivado_de</code>) and soft
            (<code>inspirado_em</code>) regulatory inheritance.
          </li>
          <li>
            <span className="text-white font-medium">Search</span> for any country ISO
            or norm fragment to dim the rest of the graph and surface matches.
          </li>
        </ul>
      </Card>
    </div>
  );
}
