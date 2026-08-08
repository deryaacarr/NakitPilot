"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { fetchDaySummary } from "@/lib/collections/api";
import type { DaySummary } from "@/lib/collections/types";
import { formatMoney } from "@/lib/customers/format";

export function DaySummaryPanel({
  refreshKey = 0,
  defaultOpen,
}: {
  refreshKey?: number;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  const [data, setData] = useState<DaySummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await fetchDaySummary("mine");
    if (!res.ok) {
      setError(res.error.message);
      return;
    }
    setError(null);
    setData(res.data);
  }, []);

  useEffect(() => {
    if (!open) return;
    void load();
  }, [open, load, refreshKey]);

  return (
    <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary">
      <header className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Gün sonu özeti</h2>
          <p className="text-xs text-muted">Bugünkü tahsilat performansınız</p>
        </div>
        <Button type="button" size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>
          {open ? "Gizle" : "Göster"}
        </Button>
      </header>
      {open ? (
        <div className="border-t border-border-default px-4 py-4">
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          {!data && !error ? <p className="text-sm text-muted">Yükleniyor…</p> : null}
          {data ? (
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Stat value={`${data.tasks_completed}`} label="görev tamamlandı" />
              <Stat value={`${data.customers_reached}`} label="müşteriye ulaşıldı" />
              <Stat value={`${data.promises_taken}`} label="ödeme sözü alındı" />
              <Stat
                value={formatMoney(data.potential_collection, data.currency)}
                label="potansiyel tahsilat"
              />
              <Stat value={`${data.callback_customers}`} label="müşteri tekrar aranacak" />
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <li className="rounded-[var(--radius-md)] bg-surface-secondary px-3 py-3">
      <p className="font-serif text-2xl tracking-tight text-foreground">{value}</p>
      <p className="mt-1 text-xs text-muted">{label}</p>
    </li>
  );
}
