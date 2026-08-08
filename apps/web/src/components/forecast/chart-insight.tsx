"use client";

import type { ForecastInsight } from "@/lib/forecast/types";

/** NP-443 — what / why / action under charts. */
export function ChartInsight({
  title,
  insight,
  fallback,
}: {
  title?: string;
  insight?: ForecastInsight | null;
  fallback?: { what: string; why: string; action: string };
}) {
  const data = insight || fallback;
  if (!data) return null;

  return (
    <div className="mt-3 space-y-1.5 rounded-[var(--radius-md)] border border-border-default bg-surface-secondary/50 px-3 py-2.5 text-xs leading-relaxed text-muted">
      {title ? <p className="text-[11px] font-semibold uppercase tracking-wide text-subtle">{title}</p> : null}
      <p>
        <span className="font-semibold text-foreground">Ne: </span>
        {data.what}
      </p>
      <p>
        <span className="font-semibold text-foreground">Neden önemli: </span>
        {data.why}
      </p>
      <p>
        <span className="font-semibold text-foreground">Aksiyon: </span>
        {data.action}
      </p>
    </div>
  );
}
