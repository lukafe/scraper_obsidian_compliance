"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  forceSimulation,
  forceManyBody,
  forceLink,
  forceCenter,
  forceCollide,
  type Simulation,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force";
import { zoom, zoomIdentity, type ZoomTransform } from "d3-zoom";
import { select } from "d3-selection";
import type { Graph, GraphNode, GraphEdge } from "@/lib/types";

const REGION_COLORS: Record<string, string> = {
  LATAM: "#34D399",
  NA: "#60A5FA",
  EU: "#A78BFA",
  APAC: "#F59E0B",
  MENA: "#F472B6",
  Africa: "#FB7185",
  Supranational: "#E83C32",
};

const RELATION_COLORS: Record<string, string> = {
  derivado_de: "#E83C32",
  inspirado_em: "#FFB300",
  referencia_cruzada: "#666",
  regulado_por: "#888",
  exige_servico: "#4CAF50",
  precede_deadline: "#03A9F4",
  aplica_se_a: "#9C27B0",
  citation: "#666",
  semantic: "#444",
};

interface Node extends SimulationNodeDatum {
  id: string;
  label: string;
  kind: "jurisdicao" | "lei";
  country?: string;
  region?: string;
  inlinks: number;
}

interface Link extends SimulationLinkDatum<Node> {
  source: string | Node;
  target: string | Node;
  type: string;
  weight: number;
}

interface Props {
  graph: Graph;
  /** Map of country ISO -> region (for colouring norms by region) */
  isoToRegion: Record<string, string>;
}

export function GraphView({ graph, isoToRegion }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [hovered, setHovered] = useState<Node | null>(null);
  const [selected, setSelected] = useState<Node | null>(null);
  const [search, setSearch] = useState("");
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const transformRef = useRef<ZoomTransform>(zoomIdentity);
  const simRef = useRef<Simulation<Node, Link> | null>(null);
  const nodesRef = useRef<Node[]>([]);
  const linksRef = useRef<Link[]>([]);
  const sizeRef = useRef({ width: 800, height: 600 });

  // Build nodes + links from the graph payload.
  const { allNodes, allLinks, edgeTypes } = useMemo(() => {
    const nodes: Node[] = graph.nodes.map((n: GraphNode) => ({
      id: n.id,
      label: n.label,
      kind: n.kind,
      country: n.country,
      region:
        n.kind === "jurisdicao"
          ? isoToRegion[n.id] ?? "Supranational"
          : n.country
            ? isoToRegion[n.country] ?? "Supranational"
            : "Supranational",
      inlinks: n.n_inlinks ?? 0,
    }));
    const nodeIds = new Set(nodes.map((n) => n.id));
    const links: Link[] = graph.edges
      .filter((e: GraphEdge) => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map((e: GraphEdge) => ({
        source: e.source,
        target: e.target,
        type: e.tipo_relacao,
        weight: e.peso ?? 0.5,
      }));
    const types = new Set(links.map((l) => l.type));
    return { allNodes: nodes, allLinks: links, edgeTypes: types };
  }, [graph, isoToRegion]);

  // Apply filters.
  const { nodes, links } = useMemo(() => {
    const filteredLinks = allLinks.filter((l) => !hiddenTypes.has(l.type));
    return { nodes: allNodes, links: filteredLinks };
  }, [allNodes, allLinks, hiddenTypes]);

  // Set up + run simulation when filters change.
  useEffect(() => {
    nodesRef.current = nodes.map((n) => ({ ...n }));
    linksRef.current = links.map((l) => ({ ...l }));
    const { width, height } = sizeRef.current;
    const sim = forceSimulation<Node>(nodesRef.current)
      .force(
        "link",
        forceLink<Node, Link>(linksRef.current)
          .id((d) => d.id)
          .distance((l) => 30 + (1 - (l.weight ?? 0.5)) * 80)
          .strength(0.4),
      )
      .force("charge", forceManyBody().strength(-60))
      .force("center", forceCenter(width / 2, height / 2))
      .force(
        "collide",
        forceCollide<Node>().radius((d) => 4 + Math.sqrt(d.inlinks + 1) * 1.5),
      )
      .alphaDecay(0.025);
    simRef.current = sim;
    return () => {
      sim.stop();
    };
  }, [nodes, links]);

  // Canvas paint loop.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const ctx: CanvasRenderingContext2D = context;

    let raf = 0;
    function paint() {
      raf = requestAnimationFrame(paint);
      const sim = simRef.current;
      if (!sim) return;
      const t = transformRef.current;
      const { width, height } = sizeRef.current;
      ctx.save();
      ctx.clearRect(0, 0, width, height);
      ctx.translate(t.x, t.y);
      ctx.scale(t.k, t.k);

      // edges
      for (const l of linksRef.current) {
        const s = l.source as Node;
        const tgt = l.target as Node;
        if (typeof s !== "object" || typeof tgt !== "object") continue;
        if (s.x == null || tgt.x == null) continue;
        const isFocused =
          selected && (s.id === selected.id || tgt.id === selected.id);
        ctx.strokeStyle = isFocused
          ? "#E83C32"
          : RELATION_COLORS[l.type] ?? "#444";
        ctx.globalAlpha = isFocused ? 0.85 : 0.18;
        ctx.lineWidth = isFocused ? 1.2 : 0.4;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y!);
        ctx.lineTo(tgt.x, tgt.y!);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      // nodes
      const searchLower = search.trim().toLowerCase();
      for (const n of nodesRef.current) {
        if (n.x == null || n.y == null) continue;
        const r = 3 + Math.sqrt(n.inlinks + 1) * 1.5;
        const matches =
          searchLower &&
          (n.id.toLowerCase().includes(searchLower) ||
            n.label.toLowerCase().includes(searchLower));
        const isSelected = selected?.id === n.id;
        const isHovered = hovered?.id === n.id;
        const fill =
          n.kind === "jurisdicao"
            ? REGION_COLORS[n.region ?? ""] ?? "#888"
            : REGION_COLORS[n.region ?? ""] ?? "#666";
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
        ctx.fillStyle = fill;
        ctx.globalAlpha = searchLower && !matches ? 0.18 : 1;
        ctx.fill();
        if (n.kind === "jurisdicao") {
          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
        if (isSelected || isHovered || matches) {
          ctx.strokeStyle = "#E83C32";
          ctx.lineWidth = 2;
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
        // label jurisdictions always; norms only when zoomed in or selected/hovered
        if (
          n.kind === "jurisdicao" ||
          isSelected ||
          isHovered ||
          t.k > 2.2 ||
          matches
        ) {
          ctx.fillStyle = "#fff";
          ctx.font = `${n.kind === "jurisdicao" ? 11 : 9}px Inter, sans-serif`;
          ctx.fillText(n.kind === "jurisdicao" ? n.id : n.label.slice(0, 32), n.x + r + 3, n.y + 3);
        }
      }
      ctx.restore();
    }
    raf = requestAnimationFrame(paint);
    return () => cancelAnimationFrame(raf);
  }, [hovered, selected, search]);

  // Pan / zoom (d3-zoom) wired to a transparent SVG overlay.
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;
    const resize = () => {
      const rect = container.getBoundingClientRect();
      sizeRef.current = { width: rect.width, height: rect.height };
      canvas.width = rect.width * window.devicePixelRatio;
      canvas.height = rect.height * window.devicePixelRatio;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const sel = select(canvas);
    const z = zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.2, 8])
      .on("zoom", (event) => {
        transformRef.current = event.transform;
      });
    sel.call(z);

    function eventToNode(evt: MouseEvent): Node | null {
      const rect = canvas!.getBoundingClientRect();
      const mx = evt.clientX - rect.left;
      const my = evt.clientY - rect.top;
      const t = transformRef.current;
      const x = (mx - t.x) / t.k;
      const y = (my - t.y) / t.k;
      let best: Node | null = null;
      let bestDist = 16; // px in world coords
      for (const n of nodesRef.current) {
        if (n.x == null || n.y == null) continue;
        const dx = n.x - x;
        const dy = n.y - y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < bestDist) {
          bestDist = d;
          best = n;
        }
      }
      return best;
    }

    const onMove = (e: MouseEvent) => setHovered(eventToNode(e));
    const onClick = (e: MouseEvent) => {
      const n = eventToNode(e);
      setSelected(n);
    };
    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("click", onClick);
    return () => {
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("click", onClick);
    };
  }, []);

  const visibleEdgeTypes = useMemo(() => Array.from(edgeTypes).sort(), [edgeTypes]);

  return (
    <div className="w-full h-[760px] flex gap-4">
      <div
        ref={containerRef}
        className="relative flex-1 bg-certik-dark border border-certik-border rounded-lg overflow-hidden"
      >
        <canvas
          ref={canvasRef}
          className="w-full h-full block cursor-grab active:cursor-grabbing"
        />
        <div className="absolute top-3 left-3 right-3 flex justify-between gap-2 pointer-events-none">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search node id or title…"
            className="pointer-events-auto px-3 py-1.5 text-xs rounded bg-certik-panel border border-certik-border text-white placeholder:text-certik-muted w-72"
          />
          <div className="text-xs text-certik-muted bg-certik-panel/70 border border-certik-border rounded px-3 py-1.5 pointer-events-none">
            {nodesRef.current.length} nodes · {linksRef.current.length} edges
          </div>
        </div>
      </div>

      <aside className="w-72 shrink-0 flex flex-col gap-4">
        <Legend />
        <RelationFilter
          types={visibleEdgeTypes}
          hidden={hiddenTypes}
          onToggle={(t) =>
            setHiddenTypes((prev) => {
              const next = new Set(prev);
              if (next.has(t)) next.delete(t);
              else next.add(t);
              return next;
            })
          }
        />
        <SelectedDetail
          node={selected}
          graph={graph}
          onClose={() => setSelected(null)}
        />
      </aside>
    </div>
  );
}

function Legend() {
  return (
    <div className="bg-certik-panel border border-certik-border rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-certik-muted mb-2">
        Region
      </div>
      <ul className="space-y-1 text-xs">
        {Object.entries(REGION_COLORS).map(([region, color]) => (
          <li key={region} className="flex items-center gap-2">
            <span
              className="inline-block w-3 h-3 rounded-full border border-white/40"
              style={{ background: color }}
            />
            <span className="text-zinc-200">{region}</span>
          </li>
        ))}
      </ul>
      <div className="mt-3 pt-3 border-t border-certik-border/60 text-[11px] text-certik-muted leading-snug">
        Larger nodes = more inlinks. Filled circle = norm; bordered circle = jurisdiction.
      </div>
    </div>
  );
}

function RelationFilter({
  types,
  hidden,
  onToggle,
}: {
  types: string[];
  hidden: Set<string>;
  onToggle: (t: string) => void;
}) {
  return (
    <div className="bg-certik-panel border border-certik-border rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-certik-muted mb-2">
        Relation types
      </div>
      <ul className="space-y-1 text-xs">
        {types.map((t) => {
          const off = hidden.has(t);
          return (
            <li key={t}>
              <button
                onClick={() => onToggle(t)}
                className={`w-full flex items-center gap-2 px-2 py-1 rounded text-left transition-colors ${
                  off
                    ? "text-zinc-500 hover:bg-certik-border/30"
                    : "text-zinc-200 hover:bg-certik-border/30"
                }`}
              >
                <span
                  className="inline-block w-2.5 h-2.5 rounded-full"
                  style={{
                    background: off
                      ? "transparent"
                      : RELATION_COLORS[t] ?? "#444",
                    border: `1px solid ${RELATION_COLORS[t] ?? "#444"}`,
                  }}
                />
                <span className="flex-1">{humanizeRelation(t)}</span>
                {off && <span className="text-[10px]">hidden</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function humanizeRelation(t: string): string {
  return (
    {
      derivado_de: "Derived from (binding)",
      inspirado_em: "Inspired by (soft)",
      referencia_cruzada: "Cross-reference",
      regulado_por: "Regulated by",
      exige_servico: "Triggers service",
      precede_deadline: "Precedes deadline",
      aplica_se_a: "Applies to",
      citation: "Citation",
      semantic: "Semantic link",
    } as Record<string, string>
  )[t] ?? t;
}

function SelectedDetail({
  node,
  graph,
  onClose,
}: {
  node: Node | null;
  graph: Graph;
  onClose: () => void;
}) {
  if (!node) {
    return (
      <div className="bg-certik-panel border border-certik-border rounded-lg p-3 text-xs text-certik-muted">
        Click any node for details and its connections.
      </div>
    );
  }
  const fullNode = graph.nodes.find((n) => n.id === node.id);
  const outgoing = graph.edges.filter((e) => e.source === node.id);
  const incoming = graph.edges.filter((e) => e.target === node.id);
  return (
    <div className="bg-certik-panel border border-certik-border rounded-lg p-3 text-xs">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-wider text-certik-muted">
            {node.kind === "jurisdicao" ? "Jurisdiction" : "Norm"} · {node.region}
          </div>
          <div className="text-sm text-white font-semibold mt-1 break-all">{node.id}</div>
          <div className="text-zinc-300 mt-1">{fullNode?.label ?? node.label}</div>
        </div>
        <button
          onClick={onClose}
          className="text-certik-muted hover:text-white text-base leading-none"
          aria-label="Close"
        >
          ×
        </button>
      </div>
      {fullNode?.regime && (
        <div className="text-zinc-400">Regime: {fullNode.regime}</div>
      )}
      {fullNode?.status_regulatorio && (
        <div className="text-zinc-400">Status: {fullNode.status_regulatorio}</div>
      )}
      {fullNode?.deadline_principal && (
        <div className="text-zinc-400">
          Deadline: {fullNode.deadline_principal}
        </div>
      )}
      <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
        <div className="bg-certik-border/30 rounded p-2">
          <div className="text-certik-muted">Outgoing</div>
          <div className="text-white text-base font-mono">{outgoing.length}</div>
        </div>
        <div className="bg-certik-border/30 rounded p-2">
          <div className="text-certik-muted">Incoming</div>
          <div className="text-white text-base font-mono">{incoming.length}</div>
        </div>
      </div>
      {node.kind === "jurisdicao" && (
        <a
          href={`/jurisdictions/${node.id}`}
          className="block mt-3 text-center text-xs text-certik-red hover:underline"
        >
          Open country profile →
        </a>
      )}
    </div>
  );
}
