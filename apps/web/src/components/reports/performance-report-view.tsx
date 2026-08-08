"use client";

import { useEffect, useState } from "react";

import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { apiRequest } from "@/lib/api/client";

export function PerformanceReportView() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await apiRequest<Record<string, unknown>>("/api/dashboard/performance/", {
        query: { range: "month" },
      });
      if (cancelled) return;
      setLoading(false);
      if (!res.ok) {
        setError(res.error.message);
        return;
      }
      setData(res.data);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <LoadingSkeleton className="h-48" />;
  if (error) return <p className="text-sm text-danger">{error}</p>;

  const metrics = Object.entries(data || {}).filter(
    ([, v]) => typeof v === "string" || typeof v === "number" || typeof v === "boolean",
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-foreground">Tahsilat performansı</h1>
        <p className="mt-1 text-sm text-muted">Dönemsel tahsilat ve aktivite özeti</p>
      </div>
      {metrics.length ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {metrics.map(([key, value]) => (
            <div
              key={key}
              className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-subtle">
                {key.replace(/_/g, " ")}
              </p>
              <p className="mt-2 text-xl font-semibold text-foreground">{String(value)}</p>
            </div>
          ))}
        </div>
      ) : null}
      <pre className="overflow-auto rounded-[var(--radius-lg)] border border-border-default bg-surface-secondary p-4 text-xs">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
