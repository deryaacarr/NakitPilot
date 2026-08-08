"use client";

import Link from "next/link";

import { Money } from "@/components/ui/money";
import { cn } from "@/lib/cn";
import type { KpiComparison } from "@/lib/dashboard/types";

type KpiCardProps = {
  label: string;
  value: string | number;
  href: string;
  isMoney?: boolean;
  currency?: string;
  subtitle?: string;
  comparison?: KpiComparison;
  className?: string;
};

function trendTone(changePct: number | null | undefined, goodWhen: "up" | "down") {
  if (changePct == null || changePct === 0) return "neutral" as const;
  const rising = changePct > 0;
  const good = goodWhen === "up" ? rising : !rising;
  return good ? ("good" as const) : ("bad" as const);
}

export function KpiCard({
  label,
  value,
  href,
  isMoney,
  currency = "TRY",
  subtitle,
  comparison,
  className,
}: KpiCardProps) {
  const tone = trendTone(comparison?.change_pct, comparison?.direction_good_when ?? "up");
  const pct = comparison?.change_pct;
  const rising = pct != null && pct > 0;

  return (
    <Link
      href={href}
      className={cn(
        "flex h-full min-h-[8.5rem] flex-col rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 transition hover:border-primary/40 hover:bg-primary/5",
        className,
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-subtle">{label}</p>
      <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
        {isMoney ? <Money value={value} currency={currency} size="metric" /> : value}
      </div>
      {pct != null ? (
        <p
          className={cn(
            "mt-2 inline-flex items-center gap-1 text-xs font-medium",
            tone === "good" && "text-success",
            tone === "bad" && "text-danger",
            tone === "neutral" && "text-muted",
          )}
        >
          <span aria-hidden>{rising ? "▲" : pct < 0 ? "▼" : "•"}</span>
          <span>
            {comparison?.label || "Önceki döneme göre"} %{Math.abs(pct).toFixed(1)}{" "}
            {rising ? "arttı" : pct < 0 ? "azaldı" : "değişmedi"}
          </span>
        </p>
      ) : (
        <p className="mt-2 text-xs text-muted">{comparison?.label || " "}</p>
      )}
      {subtitle ? <p className="mt-auto pt-2 text-xs text-muted">{subtitle}</p> : <div className="mt-auto" />}
    </Link>
  );
}
