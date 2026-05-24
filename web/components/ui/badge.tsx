import clsx from "clsx";
import { ReactNode } from "react";

const VARIANTS = {
  default: "bg-certik-border text-white",
  red: "bg-certik-red/20 text-certik-red border border-certik-red/40",
  amber: "bg-amber-500/20 text-amber-400 border border-amber-500/40",
  green: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40",
  gray: "bg-zinc-500/20 text-zinc-300 border border-zinc-500/40",
} as const;

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: ReactNode;
  variant?: keyof typeof VARIANTS;
  className?: string;
}) {
  return (
    <span className={clsx(
      "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
      VARIANTS[variant],
      className,
    )}>
      {children}
    </span>
  );
}
