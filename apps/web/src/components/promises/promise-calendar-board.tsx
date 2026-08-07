"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { fetchPromiseCalendar } from "@/lib/promises/api";
import {
  PROMISE_STATUS_LABELS,
  type PaymentPromise,
  type PromiseCalendar,
} from "@/lib/promises/types";
import { formatDate, formatMoney } from "@/lib/customers/format";
import type { AppError } from "@/lib/errors";

const GROUPS: {
  key: keyof PromiseCalendar;
  title: string;
  tone: "danger" | "brand" | "warning" | "success";
}[] = [
  { key: "today", title: "Bugünkü sözler", tone: "brand" },
  { key: "upcoming", title: "Yaklaşan sözler", tone: "warning" },
  { key: "broken", title: "Bozulan sözler", tone: "danger" },
  { key: "fulfilled", title: "Karşılanan sözler", tone: "success" },
];

export function PromiseCalendarBoard() {
  const [board, setBoard] = useState<PromiseCalendar | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);

  const load = useCallback(async () => {
    const result = await fetchPromiseCalendar();
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      setBoard(null);
      return;
    }
    setError(null);
    setBoard(result.data);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingSkeleton lines={10} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!board) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl tracking-tight text-slate-900">Ödeme sözleri</h1>
          <p className="mt-1 text-sm text-slate-600">
            Takvim görünümü — bugün, yaklaşan, bozulan, karşılanan
          </p>
        </div>
        <Link href="/collections" className="text-brand text-sm font-medium hover:underline">
          ← Tahsilat panosu
        </Link>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {GROUPS.map((group) => (
          <section key={group.key} className="rounded-xl border border-slate-200 bg-white">
            <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-900">{group.title}</h2>
              <Badge tone={group.tone}>{board[group.key].length}</Badge>
            </header>
            <div className="max-h-[26rem] space-y-2 overflow-y-auto p-3">
              {board[group.key].length === 0 ? (
                <EmptyState title="Kayıt yok" description="Bu grupta ödeme sözü yok." />
              ) : (
                board[group.key].map((promise) => (
                  <PromiseCard key={promise.id} promise={promise} />
                ))
              )}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function PromiseCard({ promise }: { promise: PaymentPromise }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">{promise.customer_name}</p>
          <p className="text-xs text-slate-500">
            {formatDate(promise.promised_date)} · {formatMoney(promise.amount, promise.currency)}
          </p>
        </div>
        <Badge
          tone={
            promise.status === "BROKEN"
              ? "danger"
              : promise.status === "FULFILLED"
                ? "success"
                : "neutral"
          }
        >
          {PROMISE_STATUS_LABELS[promise.status] ?? promise.status}
        </Badge>
      </div>
      {promise.notes ? <p className="mt-1 text-xs text-slate-600">{promise.notes}</p> : null}
    </article>
  );
}
