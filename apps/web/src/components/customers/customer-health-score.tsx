"use client";

import { useEffect, useMemo, useState } from "react";

import { StatusChip } from "@/components/ui/status-chip";
import { fetchCustomerRiskExplanation, fetchCustomerRiskHistory } from "@/lib/customers/api";
import { formatDate } from "@/lib/customers/format";
import { RISK_LABELS, type RiskExplanation, type RiskHistoryPoint } from "@/lib/customers/types";
import type { SemanticTone } from "@/lib/design/semantic";
import { cn } from "@/lib/cn";

function levelTone(level: string): SemanticTone {
  if (level === "LOW") return "success";
  if (level === "MEDIUM") return "warning";
  if (level === "HIGH" || level === "CRITICAL") return "danger";
  return "neutral";
}

export function CustomerHealthScore({ customerId }: { customerId: number }) {
  const [data, setData] = useState<RiskExplanation | null>(null);
  const [points, setPoints] = useState<RiskHistoryPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      fetchCustomerRiskExplanation(customerId),
      fetchCustomerRiskHistory(customerId, "90d"),
    ]).then(([exp, hist]) => {
      if (cancelled) return;
      if (!exp.ok) {
        setError(exp.error.message);
        return;
      }
      setError(null);
      setData(exp.data);
      if (hist.ok) setPoints(hist.data.points);
    });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  const trend = useMemo(() => {
    if (points.length < 2) return null;
    const first = points[0].score;
    const last = points[points.length - 1].score;
    const delta = last - first;
    return { first, last, delta };
  }, [points]);

  if (error) {
    return (
      <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
        <h2 className="text-sm font-semibold">Müşteri sağlık skoru</h2>
        <p className="mt-2 text-sm text-muted">{error}</p>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
        <h2 className="text-sm font-semibold">Müşteri sağlık skoru</h2>
        <p className="mt-2 text-sm text-muted">Yükleniyor…</p>
      </section>
    );
  }

  const reasons = data.reasons.filter((r) => r.sign === "+").slice(0, 5);
  const updatedAt = data.calculated_at || data.as_of;

  return (
    <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Müşteri sağlık skoru</h2>
          <p className="mt-2 font-serif text-3xl tracking-tight text-foreground">
            Risk Skoru: {data.score} <span className="text-lg text-muted">/ 100</span>
          </p>
          <div className="mt-2">
            <StatusChip
              tone={levelTone(data.level)}
              label={`${data.level_label || RISK_LABELS[data.level]} Risk`}
            />
          </div>
        </div>
        <div className="text-right text-xs text-muted">
          <p>Güncelleme</p>
          <p className="font-medium text-foreground">
            {updatedAt ? formatDateTime(updatedAt) : "—"}
          </p>
          {trend ? (
            <p
              className={cn(
                "mt-2 font-semibold",
                trend.delta > 0 && "text-danger",
                trend.delta < 0 && "text-success",
                trend.delta === 0 && "text-muted",
              )}
            >
              Son 90 gün: {trend.first} → {trend.last}{" "}
              ({trend.delta > 0 ? "+" : ""}
              {trend.delta})
            </p>
          ) : (
            <p className="mt-2">Trend için yeterli geçmiş yok</p>
          )}
        </div>
      </div>

      <div className="mt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-subtle">Nedenler</p>
        {reasons.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Belirgin olumsuz risk faktörü yok.</p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {reasons.map((reason) => (
              <li key={`${reason.code}-${reason.text}`} className="flex gap-2 text-sm text-foreground">
                <span className="text-danger" aria-hidden>
                  –
                </span>
                <span>{reason.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {points.length > 1 ? (
        <div className="mt-4">
          <MiniTrend points={points} />
        </div>
      ) : null}
    </section>
  );
}

function formatDateTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
  return d.toLocaleString("tr-TR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function MiniTrend({ points }: { points: RiskHistoryPoint[] }) {
  const w = 280;
  const h = 56;
  const pad = 4;
  const coords = points.map((p, i) => {
    const x = points.length === 1 ? w / 2 : pad + (i / (points.length - 1)) * (w - pad * 2);
    const y = pad + (1 - Math.min(100, Math.max(0, p.score)) / 100) * (h - pad * 2);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
  });
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-14 w-full" role="img" aria-label="Risk trendi">
      <path d={coords.join(" ")} fill="none" stroke="var(--color-primary)" strokeWidth="2" />
    </svg>
  );
}
