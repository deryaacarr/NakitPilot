"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { fetchCustomerRiskHistory, type RiskHistoryRange } from "@/lib/customers/api";
import type { RiskHistoryPoint } from "@/lib/customers/types";
import { cn } from "@/lib/cn";

const RANGES: { id: RiskHistoryRange; label: string }[] = [
  { id: "30d", label: "Son 30 gün" },
  { id: "90d", label: "Son 90 gün" },
  { id: "12m", label: "Son 12 ay" },
];

export function CustomerRiskHistoryChart({ customerId }: { customerId: number }) {
  const [range, setRange] = useState<RiskHistoryRange>("30d");
  const [points, setPoints] = useState<RiskHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void fetchCustomerRiskHistory(customerId, range).then((result) => {
      if (cancelled) return;
      setLoading(false);
      if (result.ok) setPoints(result.data.points);
      else setPoints([]);
    });
    return () => {
      cancelled = true;
    };
  }, [customerId, range]);

  const path = useMemo(() => buildPath(points), [points]);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-900">Risk değişimi</h2>
        <div className="flex flex-wrap gap-1">
          {RANGES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setRange(item.id)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition",
                range === item.id
                  ? "bg-brand/10 text-brand"
                  : "text-slate-600 hover:bg-slate-100",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? <LoadingSkeleton lines={4} /> : null}
      {!loading && points.length === 0 ? (
        <EmptyState
          title="Henüz geçmiş yok"
          description="Risk skoru hesaplandıkça bu grafikte görünecek."
        />
      ) : null}
      {!loading && points.length > 0 ? (
        <div className="space-y-2">
          <svg viewBox="0 0 320 120" className="h-36 w-full" role="img" aria-label="Risk skoru grafiği">
            <line x1="0" y1="30" x2="320" y2="30" stroke="#e2e8f0" strokeWidth="1" />
            <line x1="0" y1="60" x2="320" y2="60" stroke="#e2e8f0" strokeWidth="1" />
            <line x1="0" y1="90" x2="320" y2="90" stroke="#e2e8f0" strokeWidth="1" />
            {path ? (
              <path d={path} fill="none" stroke="#0f766e" strokeWidth="2.5" strokeLinejoin="round" />
            ) : null}
            {points.map((point, index) => {
              const { x, y } = pointCoord(point.score, index, points.length);
              return <circle key={`${point.at}-${index}`} cx={x} cy={y} r="3.5" fill="#0f766e" />;
            })}
          </svg>
          <div className="flex justify-between text-xs text-slate-500">
            <span>0</span>
            <span>
              Son: {points[points.length - 1]?.score} ({points[points.length - 1]?.level})
            </span>
            <span>100</span>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function pointCoord(score: number, index: number, count: number) {
  const padX = 8;
  const padY = 10;
  const width = 320 - padX * 2;
  const height = 120 - padY * 2;
  const x = count === 1 ? 160 : padX + (index / (count - 1)) * width;
  const y = padY + (1 - Math.min(100, Math.max(0, score)) / 100) * height;
  return { x, y };
}

function buildPath(points: RiskHistoryPoint[]) {
  if (points.length === 0) return "";
  return points
    .map((point, index) => {
      const { x, y } = pointCoord(point.score, index, points.length);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}
