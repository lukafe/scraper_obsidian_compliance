import { Jurisdiction } from "@/lib/types";

const TIER_STYLES: Record<string, string> = {
  high: "bg-emerald-900/30 border-emerald-600/50 text-emerald-300",
  medium: "bg-amber-900/30 border-amber-600/50 text-amber-300",
  low: "bg-zinc-800/50 border-zinc-600/50 text-zinc-400",
};

const TIER_LABELS: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export function ConfidenceBadge({
  confidence,
  showScore = true,
}: {
  confidence: Jurisdiction["data_confidence"];
  showScore?: boolean;
}) {
  const tier = confidence?.tier ?? "low";
  const score = confidence?.score ?? 0;
  return (
    <span
      title={
        confidence
          ? `Analysis coverage ${(confidence.components.analysis_coverage * 100).toFixed(0)}% · ` +
            `Coverage breadth ${(confidence.components.coverage_breadth * 100).toFixed(0)}% · ` +
            `Regulator diversity ${(confidence.components.regulator_diversity * 100).toFixed(0)}% · ` +
            `Evidence density ${(confidence.components.evidence_density * 100).toFixed(0)}%`
          : undefined
      }
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border ${TIER_STYLES[tier]}`}
    >
      <span className="uppercase tracking-wide">{TIER_LABELS[tier]}</span>
      {showScore && <span className="font-mono opacity-80">{score.toFixed(0)}</span>}
    </span>
  );
}
