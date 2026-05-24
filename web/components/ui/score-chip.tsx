/**
 * Opportunity-score chip. Coloured by tier instead of a linear opacity ramp,
 * so low scores (< 30) stay readable and the visual hierarchy matches the
 * three actionable buckets the methodology defines.
 *
 *   80-100  red    "Act now"
 *   60-79   amber  "Pipeline"
 *   40-59   muted  "Monitor"
 *    0-39   gray   "De-prioritise"
 */
export function ScoreChip({
  score,
  size = "sm",
}: {
  score: number;
  size?: "sm" | "md" | "lg";
}) {
  const palette = scorePalette(score);
  const sizing =
    size === "lg"
      ? "px-4 py-2 text-xl"
      : size === "md"
        ? "px-3 py-1 text-base"
        : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center rounded font-mono font-medium border ${palette.bg} ${palette.text} ${palette.border} ${sizing}`}
      title={`Opportunity score: ${score.toFixed(1)} / 100`}
    >
      {score.toFixed(1)}
    </span>
  );
}

function scorePalette(score: number) {
  if (score >= 80) {
    return {
      bg: "bg-certik-red/85",
      text: "text-white",
      border: "border-certik-red",
    };
  }
  if (score >= 60) {
    return {
      bg: "bg-amber-600/30",
      text: "text-amber-200",
      border: "border-amber-600/60",
    };
  }
  if (score >= 40) {
    return {
      bg: "bg-zinc-700/40",
      text: "text-zinc-200",
      border: "border-zinc-600/60",
    };
  }
  return {
    bg: "bg-zinc-800/60",
    text: "text-zinc-400",
    border: "border-zinc-700/60",
  };
}
