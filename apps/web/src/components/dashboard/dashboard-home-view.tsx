"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { cn } from "@/lib/cn";
import { fetchDashboardOverview } from "@/lib/dashboard/api";
import type { DashboardOverview, DashboardRangePreset } from "@/lib/dashboard/types";
import {
  dashboardPersona,
  isWidgetVisible,
  loadWidgetPrefs,
  type WidgetId,
} from "@/lib/dashboard/widgets";
import type { AppError } from "@/lib/errors";

import { AgentWorkboardPanels } from "./agent-workboard";
import { CallPriorityPanel } from "./call-priority-panel";
import { DashboardEmptyState } from "./dashboard-empty-state";
import { KpiCard } from "./kpi-card";
import { ManagerAnalytics } from "./manager-analytics";
import { WidgetCustomizer } from "./widget-customizer";

const RANGE_OPTIONS: { id: DashboardRangePreset; label: string }[] = [
  { id: "today", label: "Bugün" },
  { id: "week", label: "Bu hafta" },
  { id: "month", label: "Bu ay" },
  { id: "last_30", label: "Son 30 gün" },
  { id: "custom", label: "Özel aralık" },
];

export function DashboardHomeView() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [preset, setPreset] = useState<DashboardRangePreset>("week");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [visible, setVisible] = useState<WidgetId[]>([]);

  const persona = dashboardPersona(data?.role);
  const show = (id: WidgetId) => isWidgetVisible(visible, id);

  const load = useCallback(async () => {
    if (preset === "custom" && (!customFrom || !customTo)) return;
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
    const nextPersona = dashboardPersona(result.data.role);
    setVisible(loadWidgetPrefs(nextPersona));
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
        <Header persona={persona} />
        <DateFilter
          preset={preset}
          onPreset={setPreset}
          customFrom={customFrom}
          customTo={customTo}
          onFrom={setCustomFrom}
          onTo={setCustomTo}
        />
      </div>
    );
  }

  const { summary, aging, call_list, performance } = data;
  const currency = summary.currency;
  const cards = summary.cards;
  const comparisons = summary.comparisons || {};
  const meta = summary.meta;
  const isEmpty = meta?.is_empty ?? false;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Header persona={persona} />
        <WidgetCustomizer persona={persona} visible={visible} onChange={setVisible} />
      </div>

      <DateFilter
        preset={preset}
        onPreset={setPreset}
        customFrom={customFrom || data.range.date_from}
        customTo={customTo || data.range.date_to}
        onFrom={setCustomFrom}
        onTo={setCustomTo}
      />
      {loading ? <p className="text-xs text-muted">Güncelleniyor…</p> : null}

      {isEmpty ? (
        <DashboardEmptyState onSampleLoaded={() => void load()} />
      ) : (
        <>
          {/* Layer 1 — Bugün ne yapmalıyım? */}
          <div className="space-y-4">
            {show("call_priority") ? (
              <CallPriorityPanel
                rows={call_list.results}
                currency={currency}
                onChanged={() => void load()}
              />
            ) : null}

            {persona === "agent" && data.agent ? (
              <AgentWorkboardPanels
                agent={data.agent}
                currency={currency}
                show={{
                  today: show("agent_today_tasks"),
                  overdue: show("agent_overdue_tasks"),
                  promises: show("agent_promises"),
                  activities: show("agent_activities"),
                }}
              />
            ) : null}
          </div>

          {/* Layer 2 — Finansal durum */}
          {persona === "manager" && show("kpi_financial") ? (
            <section className="space-y-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-subtle">
                  Finansal durum
                </p>
                <h2 className="font-serif text-xl text-foreground">KPI’lar</h2>
              </div>
              <div className="grid auto-rows-fr gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <KpiCard
                  label="Toplam açık bakiye"
                  value={cards.open_receivables}
                  isMoney
                  currency={currency}
                  href="/invoices"
                  comparison={comparisons.open_receivables}
                  subtitle={`${meta?.open_invoice_count ?? "—"} açık fatura`}
                />
                <KpiCard
                  label="Gecikmiş alacak"
                  value={cards.overdue_receivables}
                  isMoney
                  currency={currency}
                  href="/invoices?status=OVERDUE"
                  comparison={comparisons.overdue_receivables}
                  subtitle={`${meta?.overdue_invoice_count ?? "—"} açık fatura`}
                />
                <KpiCard
                  label="Tahsilat beklentisi"
                  value={cards.expected_this_week}
                  isMoney
                  currency={currency}
                  href="/forecast"
                  comparison={comparisons.expected_this_week}
                  subtitle="Seçili dönem"
                />
                <KpiCard
                  label="Kritik müşteriler"
                  value={cards.critical_customers}
                  href="/customers?risk_status=CRITICAL"
                  comparison={comparisons.critical_customers}
                  subtitle="Anlık risk"
                />
              </div>
            </section>
          ) : null}

          {persona === "agent" && show("kpi_agent") ? (
            <section className="grid auto-rows-fr gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard
                label="Bugünkü görevler"
                value={cards.today_tasks ?? data.agent?.today_tasks.length ?? 0}
                href="/collections"
                subtitle="Vadesi bugün"
              />
              <KpiCard
                label="Gecikmiş görevler"
                value={cards.overdue_tasks}
                href="/collections/tasks"
                comparison={comparisons.overdue_tasks}
                subtitle="Takip gerekli"
              />
              <KpiCard
                label="Bugünkü ödeme sözleri"
                value={cards.promises_today}
                href="/promises"
                subtitle="Teyit et"
              />
              <KpiCard
                label="Bozulan sözler"
                value={cards.promises_broken}
                href="/promises"
                comparison={comparisons.promises_broken}
                subtitle="Dönem içi"
              />
            </section>
          ) : null}

          {/* Layer 3 — Risk ve trend */}
          {persona === "manager" ? (
            <ManagerAnalytics
              performance={performance}
              aging={aging}
              risk={data.risk_distribution}
              forecast={data.forecast}
              currency={currency}
              show={{
                performance: show("performance"),
                team: show("team_performance"),
                aging: show("aging"),
                risk: show("risk_distribution"),
                forecast: show("forecast"),
              }}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

function Header({ persona }: { persona: "manager" | "agent" }) {
  return (
    <header className="space-y-1">
      <h1 className="font-serif text-3xl tracking-tight text-foreground">
        {persona === "agent" ? "Bugünkü çalışma alanım" : "Yönetici özeti"}
      </h1>
      <p className="text-sm text-muted">
        {persona === "agent"
          ? "Önce aramalar ve görevler — gereksiz KPI yok"
          : "Kritik aksiyonlar → finansal durum → risk ve trend"}
      </p>
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
    <div className="flex flex-col gap-3 rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <div className="flex flex-wrap gap-1">
        {RANGE_OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => onPreset(opt.id)}
            className={cn(
              "rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-medium transition",
              preset === opt.id
                ? "bg-primary/10 text-primary"
                : "text-muted hover:bg-surface-tertiary hover:text-foreground",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {preset === "custom" ? (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label className="text-muted">
            Başlangıç
            <input
              type="date"
              value={customFrom}
              onChange={(e) => onFrom(e.target.value)}
              className="ml-2 rounded-[var(--radius-md)] border border-border-default px-2 py-1"
            />
          </label>
          <label className="text-muted">
            Bitiş
            <input
              type="date"
              value={customTo}
              onChange={(e) => onTo(e.target.value)}
              className="ml-2 rounded-[var(--radius-md)] border border-border-default px-2 py-1"
            />
          </label>
        </div>
      ) : null}
    </div>
  );
}
