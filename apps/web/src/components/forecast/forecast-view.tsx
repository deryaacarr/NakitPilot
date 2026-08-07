"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorState } from "@/components/errors";
import { fetchCashFlowForecast } from "@/lib/forecast/api";
import type { CashFlowForecastResponse, ForecastWeek, ForecastWeekDetail } from "@/lib/forecast/types";
import { formatDate, formatMoney } from "@/lib/customers/format";
import type { AppError } from "@/lib/errors";
import { cn } from "@/lib/cn";

const SERIES = [
  { key: "expected" as const, label: "Beklenen", color: "#0f766e" },
  { key: "optimistic" as const, label: "İyimser", color: "#059669" },
  { key: "pessimistic" as const, label: "Kötümser", color: "#b45309" },
  { key: "nominal" as const, label: "Nominal", color: "#64748b" },
];

type SeriesKey = (typeof SERIES)[number]["key"];

export function ForecastView() {
  const [data, setData] = useState<CashFlowForecastResponse | null>(null);
  const [detail, setDetail] = useState<ForecastWeekDetail | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<AppError | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchCashFlowForecast({ weeks: 13 });
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      setData(null);
      return;
    }
    setError(null);
    setData(result.data);
    const first = result.data.weeks[0]?.week_start ?? null;
    setSelectedWeek(first);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selectedWeek) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    void fetchCashFlowForecast({ weeks: 13, week_start: selectedWeek }).then((result) => {
      if (cancelled) return;
      setDetailLoading(false);
      if (result.ok && result.data.detail) setDetail(result.data.detail);
      else setDetail(null);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedWeek]);

  if (loading) return <LoadingSkeleton lines={10} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!data || data.weeks.length === 0) {
    return (
      <EmptyState
        title="Forecast yok"
        description="Açık fatura olduğunda 13 haftalık nakit akışı burada görünür."
      />
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Nakit akışı tahmini</h1>
        <p className="text-sm text-slate-600">
          Önümüzdeki 13 hafta · kural tabanlı senaryolar (ML yok)
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap gap-4 text-xs font-medium">
          {SERIES.map((s) => (
            <span key={s.key} className="inline-flex items-center gap-1.5 text-slate-700">
              <span className="inline-block size-2.5 rounded-full" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
        <ForecastChart
          weeks={data.weeks}
          selectedWeek={selectedWeek}
          onSelectWeek={setSelectedWeek}
        />
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Hafta açıklaması</h2>
          {detailLoading ? <LoadingSkeleton lines={4} /> : null}
          {!detailLoading && detail ? (
            <div className="space-y-3 text-sm text-slate-700">
              <p className="text-base font-semibold text-slate-900">{detail.summary}</p>
              <dl className="space-y-2">
                <Row label="Toplam açık fatura" value={formatMoney(detail.open_total, data.currency)} />
                <Row
                  label="Risk nedeniyle azaltılan tutar"
                  value={formatMoney(detail.risk_reduction, data.currency)}
                />
                <Row
                  label="En yüksek riskli müşteri"
                  value={
                    detail.highest_risk_customer ? (
                      <Link
                        href={`/customers/${detail.highest_risk_customer.id}`}
                        className="text-brand font-medium hover:underline"
                      >
                        {detail.highest_risk_customer.name}
                      </Link>
                    ) : (
                      "—"
                    )
                  }
                />
              </dl>
            </div>
          ) : null}
          {!detailLoading && !detail ? (
            <p className="text-sm text-slate-500">Grafikte bir haftaya tıklayın.</p>
          ) : null}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">
            Haftanın en yüksek tutarlı faturaları
          </h2>
          {detailLoading ? <LoadingSkeleton lines={5} /> : null}
          {!detailLoading && detail && detail.top_invoices.length === 0 ? (
            <EmptyState title="Fatura yok" description="Bu haftaya düşen açık fatura bulunmuyor." />
          ) : null}
          {!detailLoading && detail && detail.top_invoices.length > 0 ? (
            <ul className="divide-y divide-slate-100">
              {detail.top_invoices.map((inv) => (
                <li key={inv.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5">
                  <div>
                    <Link
                      href={`/invoices/${inv.id}`}
                      className="text-sm font-semibold text-slate-900 hover:text-brand"
                    >
                      {inv.number}
                    </Link>
                    <p className="text-xs text-slate-500">
                      {inv.customer_name} · vade {formatDate(inv.due_date)}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="font-medium text-slate-900">
                      {formatMoney(inv.open_amount, data.currency)}
                    </p>
                    <p className="text-xs text-slate-500">
                      Beklenen {formatMoney(inv.expected_amount, data.currency)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 pb-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900">{value}</dd>
    </div>
  );
}

function ForecastChart({
  weeks,
  selectedWeek,
  onSelectWeek,
}: {
  weeks: ForecastWeek[];
  selectedWeek: string | null;
  onSelectWeek: (weekStart: string) => void;
}) {
  const width = 640;
  const height = 220;
  const padX = 28;
  const padY = 16;
  const plotW = width - padX * 2;
  const plotH = height - padY * 2;

  const maxVal = useMemo(() => {
    let m = 0;
    for (const w of weeks) {
      for (const s of SERIES) {
        m = Math.max(m, Number(w[s.key]) || 0);
      }
    }
    return m || 1;
  }, [weeks]);

  const point = (index: number, value: number) => {
    const x = weeks.length === 1 ? width / 2 : padX + (index / (weeks.length - 1)) * plotW;
    const y = padY + (1 - value / maxVal) * plotH;
    return { x, y };
  };

  const pathFor = (key: SeriesKey) =>
    weeks
      .map((w, i) => {
        const { x, y } = point(i, Number(w[key]) || 0);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-56 w-full" role="img" aria-label="Nakit akışı grafiği">
      {[0.25, 0.5, 0.75].map((t) => (
        <line
          key={t}
          x1={padX}
          x2={width - padX}
          y1={padY + t * plotH}
          y2={padY + t * plotH}
          stroke="#e2e8f0"
          strokeWidth="1"
        />
      ))}
      {SERIES.map((s) => (
        <path
          key={s.key}
          d={pathFor(s.key)}
          fill="none"
          stroke={s.color}
          strokeWidth={s.key === "expected" ? 2.75 : 1.75}
          strokeDasharray={s.key === "nominal" ? "5 4" : undefined}
          strokeLinejoin="round"
          strokeLinecap="round"
          opacity={s.key === "expected" ? 1 : 0.85}
        />
      ))}
      {weeks.map((w, i) => {
        const { x } = point(i, 0);
        const selected = w.week_start === selectedWeek;
        return (
          <g key={w.week_start}>
            <rect
              x={x - plotW / weeks.length / 2}
              y={padY}
              width={Math.max(12, plotW / weeks.length)}
              height={plotH}
              fill={selected ? "rgba(15,118,110,0.08)" : "transparent"}
              className="cursor-pointer"
              onClick={() => onSelectWeek(w.week_start)}
            />
            <circle
              cx={x}
              cy={point(i, Number(w.expected) || 0).y}
              r={selected ? 5 : 3.5}
              fill="#0f766e"
              className={cn("cursor-pointer", selected && "stroke-white stroke-2")}
              onClick={() => onSelectWeek(w.week_start)}
            />
          </g>
        );
      })}
    </svg>
  );
}
