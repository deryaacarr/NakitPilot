"use client";

import Link from "next/link";
import { useMemo } from "react";

import { Money } from "@/components/ui/money";
import { formatMoney } from "@/lib/customers/format";
import { RISK_LABELS, type RiskStatus } from "@/lib/customers/types";
import type {
  AgingReport,
  ForecastSnippet,
  PerformanceReport,
  RiskDistribution,
} from "@/lib/dashboard/types";
import { cn } from "@/lib/cn";

export function ManagerAnalytics({
  performance,
  aging,
  risk,
  forecast,
  currency,
  show,
}: {
  performance: PerformanceReport;
  aging: AgingReport;
  risk?: RiskDistribution;
  forecast?: ForecastSnippet;
  currency: string;
  show: {
    performance: boolean;
    team: boolean;
    aging: boolean;
    risk: boolean;
    forecast: boolean;
  };
}) {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-subtle">Risk ve trend</p>
        <h2 className="font-serif text-xl text-foreground">Grafikler ve analizler</h2>
      </div>

      {(show.performance || show.team) && (
        <PerformanceBlock performance={performance} currency={currency} showChart={show.performance} showTeam={show.team} />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {show.aging ? <AgingBlock aging={aging} currency={currency} /> : null}
        {show.risk && risk ? <RiskBlock risk={risk} /> : null}
        {show.forecast && forecast ? <ForecastBlock forecast={forecast} /> : null}
      </div>
    </div>
  );
}

function PerformanceBlock({
  performance,
  currency,
  showChart,
  showTeam,
}: {
  performance: PerformanceReport;
  currency: string;
  showChart: boolean;
  showTeam: boolean;
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
        <h3 className="text-sm font-semibold text-foreground">Tahsilat performansı</h3>
        <p className="text-xs text-muted">
          Gerçekleşen {formatMoney(performance.totals.actual, currency)} · Beklenen{" "}
          {formatMoney(performance.totals.expected, currency)}
        </p>
      </div>
      <div className={cn("grid gap-4", showChart && showTeam ? "lg:grid-cols-3" : "lg:grid-cols-1")}>
        {showChart ? (
          <div className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 lg:col-span-2">
            <ExpectedActualChart weeks={performance.weekly} />
          </div>
        ) : null}
        {showTeam ? (
          <div className="space-y-4">
            <div className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
              <h4 className="mb-3 text-sm font-semibold">Ödeme sözleri</h4>
              <div className="flex h-3 overflow-hidden rounded-full bg-surface-tertiary">
                <div className="bg-success" style={{ width: `${(kept / promiseTotal) * 100}%` }} />
                <div className="bg-warning" style={{ width: `${(broken / promiseTotal) * 100}%` }} />
              </div>
              <dl className="mt-3 space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted">Tutulan</dt>
                  <dd className="font-medium">{kept}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Bozulan</dt>
                  <dd className="font-medium">{broken}</dd>
                </div>
              </dl>
            </div>
            <div className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
              <h4 className="mb-3 text-sm font-semibold">Ekip performansı</h4>
              {performance.tasks_by_user.length === 0 ? (
                <p className="text-sm text-muted">Bu dönemde tamamlanan görev yok.</p>
              ) : (
                <ul className="space-y-2">
                  {performance.tasks_by_user.map((row) => (
                    <li key={`${row.user_id}-${row.user_name}`} className="text-sm">
                      <div className="mb-0.5 flex justify-between gap-2">
                        <span className="truncate text-muted">{row.user_name}</span>
                        <span className="font-medium">{row.completed_count}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded bg-surface-tertiary">
                        <div
                          className="h-full bg-primary"
                          style={{ width: `${(row.completed_count / maxBar) * 100}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function AgingBlock({ aging, currency }: { aging: AgingReport; currency: string }) {
  return (
    <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Yaşlandırma</h3>
        <Link href="/dashboard/reports/aging" className="text-xs text-primary hover:underline">
          Detay
        </Link>
      </div>
      <p className="mb-3 text-xs text-muted">
        Toplam <Money value={aging.total_open_amount} currency={currency} size="table" />
      </p>
      <ul className="space-y-2">
        {aging.groups.map((g) => (
          <li key={g.code} className="text-sm">
            <div className="mb-0.5 flex justify-between gap-2">
              <span className="text-muted">{g.label}</span>
              <span className="font-medium">
                <Money value={g.open_amount} currency={currency} size="table" />
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded bg-surface-tertiary">
              <div className="h-full bg-primary" style={{ width: `${Math.min(100, g.share_percent)}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RiskBlock({ risk }: { risk: RiskDistribution }) {
  const total = risk.groups.reduce((s, g) => s + g.count, 0) || 1;
  return (
    <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Risk dağılımı</h3>
        <Link href="/dashboard/risk-monitoring" className="text-xs text-primary hover:underline">
          Detay
        </Link>
      </div>
      <ul className="space-y-2">
        {risk.groups.map((g) => (
          <li key={g.status} className="flex items-center justify-between text-sm">
            <span className="text-muted">{RISK_LABELS[g.status as RiskStatus] ?? g.status}</span>
            <span className="font-medium">
              {g.count}{" "}
              <span className="text-xs text-subtle">(%{((g.count / total) * 100).toFixed(0)})</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ForecastBlock({ forecast }: { forecast: ForecastSnippet }) {
  return (
    <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 lg:col-span-2">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Forecast</h3>
        <Link href="/forecast" className="text-xs text-primary hover:underline">
          Nakit akışı
        </Link>
      </div>
      <p className="mb-3 text-sm text-muted">
        4 haftalık beklenen: <Money value={forecast.total_expected} currency={forecast.currency} />
      </p>
      <div className="grid gap-2 sm:grid-cols-4">
        {forecast.weeks.map((w) => (
          <div key={w.week_start} className="rounded-[var(--radius-md)] bg-surface-secondary px-3 py-2">
            <p className="text-[11px] text-subtle">{w.week_start}</p>
            <p className="mt-1 text-sm font-semibold">
              <Money value={w.expected_amount} currency={forecast.currency} size="table" />
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ExpectedActualChart({ weeks }: { weeks: PerformanceReport["weekly"] }) {
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
    return <p className="text-sm text-muted">Haftalık veri yok.</p>;
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
          stroke="var(--border-default)"
        />
      ))}
      <path d={path("expected")} fill="none" stroke="var(--color-primary)" strokeWidth="2.5" strokeLinejoin="round" />
      <path
        d={path("actual")}
        fill="none"
        stroke="var(--color-muted, #64748b)"
        strokeWidth="2"
        strokeDasharray="5 4"
        strokeLinejoin="round"
      />
    </svg>
  );
}
