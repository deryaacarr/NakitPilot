"use client";

import { useEffect, useState } from "react";

import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { Money } from "@/components/ui/money";
import { apiRequest } from "@/lib/api/client";

type AgingGroup = {
  code: string;
  label: string;
  invoice_count: number;
  open_amount: string;
  share?: string;
};

type AgingPayload = {
  as_of?: string;
  groups?: AgingGroup[];
  total_open_amount?: string;
};

export function AgingReportView() {
  const [data, setData] = useState<AgingPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await apiRequest<AgingPayload>("/api/dashboard/aging/");
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

  const groups = data?.groups || [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-foreground">Yaşlandırma</h1>
        <p className="mt-1 text-sm text-muted">
          Açık alacakların vade dilimlerine göre dağılımı
          {data?.as_of ? ` · ${data.as_of}` : ""}
        </p>
      </div>
      {data?.total_open_amount ? (
        <p className="text-sm text-muted">
          Toplam açık: <Money value={data.total_open_amount} />
        </p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {groups.map((g) => (
          <div
            key={g.code}
            className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-subtle">{g.label}</p>
            <p className="mt-2">
              <Money value={g.open_amount} size="metric" />
            </p>
            <p className="mt-1 text-xs text-muted">{g.invoice_count} fatura</p>
          </div>
        ))}
      </div>
    </div>
  );
}
