import clsx from "clsx";
import { ReactNode } from "react";

export function Card({
  children,
  className,
  title,
  subtitle,
  accent = false,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  accent?: boolean;
}) {
  return (
    <section
      className={clsx(
        "bg-certik-panel border border-certik-border rounded-lg p-5",
        accent && "border-l-4 border-l-certik-red",
        className,
      )}
    >
      {title && (
        <header className="mb-3">
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          {subtitle && <p className="text-sm text-certik-muted mt-1">{subtitle}</p>}
        </header>
      )}
      {children}
    </section>
  );
}

export function Kpi({
  label,
  value,
  hint,
  accent = false,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={clsx(
        "bg-certik-panel border border-certik-border rounded-lg p-4",
        accent && "border-l-4 border-l-certik-red",
      )}
    >
      <div className="text-xs uppercase tracking-wider text-certik-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-white">{value}</div>
      {hint && <div className="mt-1 text-xs text-certik-muted">{hint}</div>}
    </div>
  );
}
