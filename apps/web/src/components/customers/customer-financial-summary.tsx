"use client";

import { useEffect, useMemo, useState } from "react";

import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { Money } from "@/components/ui/money";
import { fetchCustomerFinancialSummary } from "@/lib/customers/api";
import type { CustomerFinancialSummary, FinancialSummarySeries } from "@/lib/customers/types";

export function CustomerFinancialSummaryPanel({ customerId }: { customerId: number }) {
  const [data, setData] = useState<CustomerFinancialSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchCustomerFinancialSummary(customerId, 12).then((res) => {
      if (cancelled) return;
      if (!res.ok) {
        setError(res.error.message);
        return;
      }
      setError(null);
      setData(res.data);
    });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!data) return <LoadingSkeleton lines={8} />;

  return (
    <div className="space-y-4">
      {data.insights.length ? (
        <div className="rounded-[var(--radius-lg)] border border-primary/20 bg-primary/5 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Özet</p>
          <ul className="mt-2 space-y-1 text-sm text-foreground">
            {data.insights.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Aylık fatura toplamı"
          caption="Dönemsel faturalanan tutar"
          series={data.monthly_invoices}
          currency={data.currency}
          mode="amount"
        />
        <ChartCard
          title="Aylık ödeme toplamı"
          caption="Dönemsel tahsil edilen tutar"
          series={data.monthly_payments}
          currency={data.currency}
          mode="amount"
        />
        <ChartCard
          title="Açık bakiye trendi"
          caption="Ay sonu yaklaşık açık alacak"
          series={data.open_balance_trend}
          currency={data.currency}
          mode="amount"
        />
        <ChartCard
          title="Ortalama ödeme gecikmesi"
          caption="Tamamlanan faturaların gecikme ortalaması (gün)"
          series={data.avg_delay_trend}
          mode="days"
        />
        <ChartCard
          title="Zamanında ödeme oranı"
          caption="Ay içinde kapanan faturalarda vadesinde ödeme oranı"
          series={data.on_time_payment_rate}
          mode="rate"
          className="lg:col-span-2"
        />
      </div>
    </div>
  );
}

function ChartCard({
  title,
  caption,
  series,
  currency = "TRY",
  mode,
  className,
}: {
  title: string;
  caption: string;
  series: FinancialSummarySeries[];
  currency?: string;
  mode: "amount" | "days" | "rate";
  className?: string;
}) {
  const values = useMemo(() => {
    return series.map((s) => {
      if (mode === "amount") return Number(s.amount || 0);
      if (mode === "days") return Number(s.days ?? 0);
      return Number(s.rate ?? 0) * 100;
    });
  }, [series, mode]);

  const max = Math.max(...values, 1);
  const last = series[series.length - 1];
  const lastLabel =
    mode === "amount" ? (
      <Money value={last?.amount} currency={currency} size="table" />
    ) : mode === "days" ? (
      `${last?.days ?? "—"} gün`
    ) : last?.rate == null ? (
      "—"
    ) : (
      `%${(Number(last.rate) * 100).toFixed(0)}`
    );

  return (
    <section
      className={`rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 ${className || ""}`}
    >
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <span className="text-sm font-semibold text-foreground">{lastLabel}</span>
      </div>
      <p className="mb-3 text-xs text-muted">{caption}</p>
      <div className="flex h-28 items-end gap-1">
        {series.map((s, i) => {
          const v = values[i] || 0;
          const h = Math.max(4, (v / max) * 100);
          return (
            <div key={s.month} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="w-full rounded-t bg-primary/80"
                style={{ height: `${h}%` }}
                title={`${s.month}: ${v}`}
              />
              <span className="text-[9px] text-subtle">{s.month.slice(5)}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
