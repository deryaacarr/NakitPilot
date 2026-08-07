"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { fetchDashboardOverview } from "@/lib/dashboard/api";
import type {
  AgingGroup,
  CallListRow,
  DashboardOverview,
  DashboardRangePreset,
  PerformanceReport,
} from "@/lib/dashboard/types";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { RISK_LABELS, type RiskStatus } from "@/lib/customers/types";
import type { AppError } from "@/lib/errors";
import { cn } from "@/lib/cn";

const RANGE_OPTIONS: { id: DashboardRangePreset; label: string }[] = [
  { id: "today", label: "Bugün" },
  { id: "week", label: "Bu hafta" },
  { id: "month", label: "Bu ay" },
  { id: "last_30", label: "Son 30 gün" },
  { id: "custom", label: "Özel aralık" },
];

function riskTone(status: string) {
  if (status === "LOW") return "success" as const;
  if (status === "MEDIUM") return "warning" as const;
  if (status === "HIGH" || status === "CRITICAL") return "danger" as const;
  return "neutral" as const;
}

export function DashboardHomeView() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [preset, setPreset] = useState<DashboardRangePreset>("week");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const load = useCallback(async () => {
    if (preset === "custom" && (!customFrom || !customTo)) {
      return;
    }
    setLoading(true);
    const result = await fetchDashboardOverview({
      range: preset,
      from: preset === "custom" ? customFrom : undefined,
      to: preset === "custom" ? customTo : undefined,
    });
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      setData(null);
      return;
    }
    setError(null);
    setData(result.data);
  }, [preset, customFrom, customTo]);

  useEffect(() => {
    if (preset === "custom" && (!customFrom || !customTo)) return;
    void load();
  }, [load, preset, customFrom, customTo]);

  if (loading && !data) return <LoadingSkeleton lines={12} />;
  if (error && !data) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!data) {
    return (
      <div className="space-y-4">
        <Header />
        <DateFilter
          preset={preset}
          onPreset={setPreset}
          customFrom={customFrom}
          customTo={customTo}
          onFrom={setCustomFrom}
          onTo={setCustomTo}
        />
        {preset === "custom" ? (
          <p className="text-sm text-slate-500">Özel aralık için başlangıç ve bitiş tarihi seçin.</p>
        ) : null}
      </div>
    );
  }

  const { summary, aging, call_list, performance, range } = data;
  const currency = summary.currency;
  const cards = summary.cards;

  return (
    <div className="space-y-8">
      <Header />
      <DateFilter
        preset={preset}
        onPreset={setPreset}
        customFrom={customFrom || range.date_from}
        customTo={customTo || range.date_to}
        onFrom={setCustomFrom}
        onTo={setCustomTo}
      />
      {loading ? <p className="text-xs text-slate-500">Güncelleniyor…</p> : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Toplam açık alacak"
          value={formatMoney(cards.open_receivables, currency)}
          href="/invoices"
        />
        <StatCard
          label="Toplam gecikmiş alacak"
          value={formatMoney(cards.overdue_receivables, currency)}
          href="/invoices?status=OVERDUE"
        />
        <StatCard
          label="Dönem beklenen tahsilat"
          value={formatMoney(cards.expected_this_week, currency)}
          href="/forecast"
        />
        <StatCard
          label="Dönemdeki ödeme sözleri"
          value={String(cards.promises_today)}
          href="/promises"
        />
        <StatCard
          label="Bozulan ödeme sözleri"
          value={String(cards.promises_broken)}
          href="/promises"
        />
        <StatCard
          label="Kritik müşteriler"
          value={String(cards.critical_customers)}
          href="/customers?risk_status=CRITICAL"
        />
        <StatCard label="Gecikmiş görevler" value={String(cards.overdue_tasks)} href="/collections" />
      </section>

      <PerformanceSection performance={performance} currency={currency} />

      <section className="space-y-3">
        <div className="flex items-end justify-between gap-2">
          <h2 className="font-serif text-xl text-slate-900">Yaşlandırma</h2>
          <p className="text-xs text-slate-500">
            Toplam {formatMoney(aging.total_open_amount, currency)}
          </p>
        </div>
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs tracking-wide text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-3 font-medium">Grup</th>
                <th className="px-4 py-3 font-medium">Müşteri</th>
                <th className="px-4 py-3 font-medium">Fatura</th>
                <th className="px-4 py-3 font-medium">Açık tutar</th>
                <th className="px-4 py-3 font-medium">Oran</th>
              </tr>
            </thead>
            <tbody>
              {aging.groups.map((group) => (
                <AgingRow key={group.code} group={group} currency={currency} />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-end justify-between gap-2">
          <h2 className="font-serif text-xl text-slate-900">Bugün aranması gerekenler</h2>
          <p className="text-xs text-slate-500">Öncelik skoruna göre ilk 10</p>
        </div>
        {call_list.results.length === 0 ? (
          <EmptyState title="Liste boş" description="Açık bakiyeli öncelikli müşteri yok." />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs tracking-wide text-slate-500 uppercase">
                <tr>
                  <th className="px-4 py-3 font-medium">Müşteri</th>
                  <th className="px-4 py-3 font-medium">Gecikmiş bakiye</th>
                  <th className="px-4 py-3 font-medium">En eski gecikme</th>
                  <th className="px-4 py-3 font-medium">Risk</th>
                  <th className="px-4 py-3 font-medium">Son görüşme</th>
                  <th className="px-4 py-3 font-medium">Ödeme sözü</th>
                  <th className="px-4 py-3 font-medium">Aksiyon</th>
                </tr>
              </thead>
              <tbody>
                {call_list.results.map((row) => (
                  <CallRow key={row.customer_id} row={row} currency={currency} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Header() {
  return (
    <header className="space-y-1">
      <h1 className="font-serif text-3xl tracking-tight text-slate-900">Özet</h1>
      <p className="text-sm text-slate-600">Tahsilat sağlığı, performans ve bugün aranacaklar</p>
    </header>
  );
}

function DateFilter({
  preset,
  onPreset,
  customFrom,
  customTo,
  onFrom,
  onTo,
}: {
  preset: DashboardRangePreset;
  onPreset: (p: DashboardRangePreset) => void;
  customFrom: string;
  customTo: string;
  onFrom: (v: string) => void;
  onTo: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <div className="flex flex-wrap gap-1">
        {RANGE_OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => onPreset(opt.id)}
            className={cn(
              "rounded-md px-3 py-1.5 text-xs font-medium transition",
              preset === opt.id ? "bg-brand/10 text-brand" : "text-slate-600 hover:bg-slate-100",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {preset === "custom" ? (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label className="text-slate-500">
            Başlangıç
            <input
              type="date"
              value={customFrom}
              onChange={(e) => onFrom(e.target.value)}
              className="ml-2 rounded-md border border-slate-300 px-2 py-1"
            />
          </label>
          <label className="text-slate-500">
            Bitiş
            <input
              type="date"
              value={customTo}
              onChange={(e) => onTo(e.target.value)}
              className="ml-2 rounded-md border border-slate-300 px-2 py-1"
            />
          </label>
        </div>
      ) : null}
    </div>
  );
}

function PerformanceSection({
  performance,
  currency,
}: {
  performance: PerformanceReport;
  currency: string;
}) {
  const maxBar = useMemo(() => {
    let m = 0;
    for (const u of performance.tasks_by_user) m = Math.max(m, u.completed_count);
    return m || 1;
  }, [performance.tasks_by_user]);

  const kept = performance.promises.kept;
  const broken = performance.promises.broken;
  const promiseTotal = kept + broken || 1;

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h2 className="font-serif text-xl text-slate-900">Tahsilat performansı</h2>
        <p className="text-xs text-slate-500">
          Gerçekleşen {formatMoney(performance.totals.actual, currency)} · Beklenen{" "}
          {formatMoney(performance.totals.expected, currency)}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-2">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">Haftalık beklenen / gerçekleşen</h3>
          <ExpectedActualChart weeks={performance.weekly} />
          <div className="mt-2 flex gap-4 text-xs text-slate-600">
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2.5 rounded-full bg-teal-700" /> Beklenen
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2.5 rounded-full bg-slate-500" /> Gerçekleşen
            </span>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">Ödeme sözleri</h3>
            <div className="flex h-3 overflow-hidden rounded-full bg-slate-100">
              <div
                className="bg-teal-700"
                style={{ width: `${(kept / promiseTotal) * 100}%` }}
                title={`Tutulan ${kept}`}
              />
              <div
                className="bg-amber-700"
                style={{ width: `${(broken / promiseTotal) * 100}%` }}
                title={`Bozulan ${broken}`}
              />
            </div>
            <dl className="mt-3 space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Tutulan</dt>
                <dd className="font-medium text-slate-900">{kept}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Bozulan</dt>
                <dd className="font-medium text-slate-900">{broken}</dd>
              </div>
            </dl>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">Tamamlanan görevler</h3>
            {performance.tasks_by_user.length === 0 ? (
              <p className="text-sm text-slate-500">Bu dönemde tamamlanan görev yok.</p>
            ) : (
              <ul className="space-y-2">
                {performance.tasks_by_user.map((row) => (
                  <li key={`${row.user_id}-${row.user_name}`} className="text-sm">
                    <div className="mb-0.5 flex justify-between gap-2">
                      <span className="truncate text-slate-700">{row.user_name}</span>
                      <span className="font-medium text-slate-900">{row.completed_count}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded bg-slate-100">
                      <div
                        className="h-full bg-brand"
                        style={{ width: `${(row.completed_count / maxBar) * 100}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function ExpectedActualChart({
  weeks,
}: {
  weeks: PerformanceReport["weekly"];
}) {
  const width = 560;
  const height = 180;
  const padX = 24;
  const padY = 16;
  const plotW = width - padX * 2;
  const plotH = height - padY * 2;

  const maxVal = useMemo(() => {
    let m = 0;
    for (const w of weeks) {
      m = Math.max(m, Number(w.actual) || 0, Number(w.expected) || 0);
    }
    return m || 1;
  }, [weeks]);

  const point = (index: number, value: number) => {
    const x = weeks.length <= 1 ? width / 2 : padX + (index / (weeks.length - 1)) * plotW;
    const y = padY + (1 - value / maxVal) * plotH;
    return { x, y };
  };

  const path = (key: "actual" | "expected") =>
    weeks
      .map((w, i) => {
        const { x, y } = point(i, Number(w[key]) || 0);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");

  if (weeks.length === 0) {
    return <p className="text-sm text-slate-500">Haftalık veri yok.</p>;
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full" role="img" aria-label="Performans grafiği">
      {[0.25, 0.5, 0.75].map((t) => (
        <line
          key={t}
          x1={padX}
          x2={width - padX}
          y1={padY + t * plotH}
          y2={padY + t * plotH}
          stroke="#e2e8f0"
        />
      ))}
      <path d={path("expected")} fill="none" stroke="#0f766e" strokeWidth="2.5" strokeLinejoin="round" />
      <path
        d={path("actual")}
        fill="none"
        stroke="#64748b"
        strokeWidth="2"
        strokeDasharray="5 4"
        strokeLinejoin="round"
      />
      {weeks.map((w, i) => {
        const a = point(i, Number(w.actual) || 0);
        const e = point(i, Number(w.expected) || 0);
        return (
          <g key={w.week_start}>
            <circle cx={e.x} cy={e.y} r="3.5" fill="#0f766e" />
            <circle cx={a.x} cy={a.y} r="3" fill="#64748b" />
          </g>
        );
      })}
    </svg>
  );
}

function StatCard({ label, value, href }: { label: string; value: string; href: string }) {
  return (
    <Link
      href={href}
      className="rounded-xl border border-slate-200 bg-white px-4 py-3 transition hover:border-teal-200 hover:bg-teal-50/40"
    >
      <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
    </Link>
  );
}

function AgingRow({ group, currency }: { group: AgingGroup; currency: string }) {
  return (
    <tr className="border-b border-slate-100 last:border-0">
      <td className="px-4 py-3 font-medium text-slate-900">{group.label}</td>
      <td className="px-4 py-3 text-slate-700">{group.customer_count}</td>
      <td className="px-4 py-3 text-slate-700">{group.invoice_count}</td>
      <td className="px-4 py-3 text-slate-900">{formatMoney(group.open_amount, currency)}</td>
      <td className="px-4 py-3">
        <div className="flex min-w-[8rem] items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded bg-slate-100">
            <div
              className="h-full bg-brand"
              style={{ width: `${Math.min(100, group.share_percent)}%` }}
            />
          </div>
          <span className="w-12 text-right text-xs text-slate-500">
            %{group.share_percent.toFixed(1)}
          </span>
        </div>
      </td>
    </tr>
  );
}

function CallRow({ row, currency }: { row: CallListRow; currency: string }) {
  const risk = row.risk_status as RiskStatus;
  return (
    <tr className="border-b border-slate-100 last:border-0">
      <td className="px-4 py-3">
        <Link href={`/customers/${row.customer_id}`} className="font-semibold text-slate-900 hover:text-brand">
          {row.customer_name}
        </Link>
        {row.customer_code ? <p className="text-xs text-slate-500">{row.customer_code}</p> : null}
      </td>
      <td className="px-4 py-3 text-slate-900">{formatMoney(row.overdue_balance, currency)}</td>
      <td className="px-4 py-3 text-slate-700">
        {row.oldest_overdue_days == null ? "—" : `${row.oldest_overdue_days} gün`}
      </td>
      <td className="px-4 py-3">
        <Badge tone={riskTone(row.risk_status)}>
          {RISK_LABELS[risk] ?? row.risk_status} · {row.risk_score}
        </Badge>
      </td>
      <td className="px-4 py-3 text-slate-700">
        {row.last_contact_at ? formatDate(row.last_contact_at.slice(0, 10)) : "—"}
      </td>
      <td className="px-4 py-3 text-slate-700">
        {row.payment_promise ? formatMoney(row.payment_promise.amount, currency) : "—"}
      </td>
      <td className="px-4 py-3">
        <Link
          href={`/collections?customer=${row.customer_id}`}
          className="border-brand text-brand inline-flex h-8 items-center rounded-lg border px-3 text-xs font-semibold hover:bg-teal-50"
        >
          Ara
        </Link>
      </td>
    </tr>
  );
}
