"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { ChartInsight } from "@/components/forecast/chart-insight";
import { ErrorState } from "@/components/errors";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ChartSkeleton, LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";
import { listCustomers } from "@/lib/customers/api";
import { formatDate, formatMoney } from "@/lib/customers/format";
import type { Customer } from "@/lib/customers/types";
import type { AppError } from "@/lib/errors";
import { fetchCashFlowForecast, runForecastScenario } from "@/lib/forecast/api";
import type {
  CashFlowForecastResponse,
  ForecastWeek,
  ForecastWeekDetail,
} from "@/lib/forecast/types";

export function ForecastView() {
  const { toast } = useToast();
  const [data, setData] = useState<CashFlowForecastResponse | null>(null);
  const [detail, setDetail] = useState<ForecastWeekDetail | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<AppError | null>(null);

  // NP-442 what-if
  const [delayDelta, setDelayDelta] = useState(0);
  const [probDelta, setProbDelta] = useState(0);
  const [excludeCustomer, setExcludeCustomer] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [scenarioLine, setScenarioLine] = useState<number[] | null>(null);
  const [scenarioBusy, setScenarioBusy] = useState(false);

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
    void listCustomers({ page_size: 100 }).then((res) => {
      if (res.ok) setCustomers(res.data.results || []);
    });
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

  async function applyWhatIf() {
    setScenarioBusy(true);
    const factor = Math.max(0.1, 1 + probDelta / 100);
    const res = await runForecastScenario({
      scenario_type: "CUSTOM",
      weeks: 13,
      variables: {
        average_delay_days_delta: delayDelta,
        collection_probability_factor: factor,
        non_paying_customer_ids: excludeCustomer ? [Number(excludeCustomer)] : [],
      },
    });
    setScenarioBusy(false);
    if (!res.ok) {
      toast({
        title: "Senaryo uygulanamadı",
        description: res.error.message,
        tone: "error",
      });
      return;
    }
    const timeline = res.data.timeline || [];
    setScenarioLine(timeline.map((t) => Number(t.expected_collection) || 0));
    toast({ title: "What-if senaryosu güncellendi", tone: "success" });
  }

  if (loading) return <ChartSkeleton />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!data || data.weeks.length === 0) {
    return (
      <EmptyState
        title="Henüz forecast oluşturulamadı."
        description="Açık fatura olduğunda 13 haftalık nakit akışı burada görünür."
        why="Tahmin, tahsilat planı ve nakit sıkışıklığını erken gösterir."
        actionLabel="Faturalara Git"
        actionHref="/invoices"
      />
    );
  }

  const vsLabel =
    detail?.vs_previous_week_pct == null
      ? "—"
      : `${detail.vs_previous_week_pct > 0 ? "+" : ""}${detail.vs_previous_week_pct}%`;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-serif text-3xl tracking-tight text-foreground">Nakit akışı tahmini</h1>
        <p className="text-sm text-muted">13 haftalık forecast · belirsizlik bandı ve what-if</p>
      </header>

      <div className="grid gap-4 xl:grid-cols-[1fr_20rem]">
        <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
          <div className="mb-3 flex flex-wrap gap-4 text-xs font-medium">
            <Legend color="#0f766e" label="Beklenen" />
            <Legend color="#059669" label="İyimser" dashed />
            <Legend color="#b45309" label="Kötümser" dashed />
            <Legend color="#334155" label="Gerçekleşen" />
            <Legend color="#94a3b8" label="Belirsizlik alanı" band />
            {scenarioLine ? <Legend color="#0e7490" label="What-if" /> : null}
          </div>
          <ForecastChart
            weeks={data.weeks}
            selectedWeek={selectedWeek}
            onSelectWeek={setSelectedWeek}
            scenarioLine={scenarioLine}
            currency={data.currency}
          />
          <ChartInsight
            insight={detail?.insight}
            fallback={{
              what: "13 haftalık beklenen tahsilat; iyimser–kötümser bandı belirsizliği gösterir.",
              why: "Nakit planlaması ve tahsilat önceliği için haftalık görünürlük sağlar.",
              action: "Haftaya tıklayıp yüksek riskli faturalar için görev oluşturun.",
            }}
          />
        </section>

        {/* NP-441 explanation panel */}
        <aside className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
          <h2 className="text-sm font-semibold text-foreground">Hafta özeti</h2>
          {detailLoading ? <LoadingSkeleton lines={5} /> : null}
          {!detailLoading && detail ? (
            <dl className="mt-3 space-y-3 text-sm">
              <PanelRow
                label="Bu hafta beklenen tahsilat"
                value={formatMoney(detail.expected, data.currency)}
              />
              <PanelRow
                label="Yüksek riskli tutar"
                value={formatMoney(detail.high_risk_amount || "0", data.currency)}
              />
              <PanelRow
                label="En büyük risk"
                value={
                  detail.highest_risk_customer ? (
                    <Link
                      href={`/customers/${detail.highest_risk_customer.id}`}
                      className="font-semibold text-brand hover:underline"
                    >
                      {detail.highest_risk_customer.name}
                    </Link>
                  ) : (
                    "—"
                  )
                }
              />
              <PanelRow label="Geçen haftaya göre" value={vsLabel} />
            </dl>
          ) : null}
          {!detailLoading && !detail ? (
            <p className="mt-3 text-sm text-muted">Grafikte bir haftaya tıklayın.</p>
          ) : null}
        </aside>
      </div>

      {/* NP-442 what-if */}
      <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
        <h2 className="text-sm font-semibold text-foreground">What-if senaryosu</h2>
        <p className="mt-1 text-xs text-muted">
          Gecikme, olasılık ve müşteri dışlama etkisini görsel test edin.
        </p>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <label className="block space-y-2 text-sm">
            <span className="font-medium">
              Tahsilat gecikmesi: {delayDelta >= 0 ? "+" : ""}
              {delayDelta} gün
            </span>
            <input
              type="range"
              min={-14}
              max={30}
              step={1}
              value={delayDelta}
              onChange={(e) => setDelayDelta(Number(e.target.value))}
              className="w-full"
            />
          </label>
          <label className="block space-y-2 text-sm">
            <span className="font-medium">
              Tahsilat olasılığı: {probDelta >= 0 ? "+" : ""}
              {probDelta}%
            </span>
            <input
              type="range"
              min={-40}
              max={20}
              step={5}
              value={probDelta}
              onChange={(e) => setProbDelta(Number(e.target.value))}
              className="w-full"
            />
          </label>
          <label className="block space-y-2 text-sm">
            <span className="font-medium">Müşteri ödemesini çıkar</span>
            <select
              value={excludeCustomer}
              onChange={(e) => setExcludeCustomer(e.target.value)}
              className="h-10 w-full rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3"
            >
              <option value="">Yok</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button type="button" loading={scenarioBusy} onClick={() => void applyWhatIf()}>
            Senaryoyu uygula
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setDelayDelta(0);
              setProbDelta(0);
              setExcludeCustomer("");
              setScenarioLine(null);
            }}
          >
            Sıfırla
          </Button>
        </div>
        <ChartInsight
          fallback={{
            what: "What-if kaydırıcıları gecikme, olasılık ve müşteri dışlama senaryolarını karşılaştırır.",
            why: "Nakit açığı riskini erken görmenizi sağlar.",
            action: "Olumsuz senaryoda riskli müşteriler için önceden takip görevi açın.",
          }}
        />
      </section>

      <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">
          Haftanın faturaları
        </h2>
        {detailLoading ? <LoadingSkeleton lines={5} /> : null}
        {!detailLoading && detail && detail.top_invoices.length === 0 ? (
          <EmptyState title="Fatura yok" description="Bu haftaya düşen açık fatura bulunmuyor." />
        ) : null}
        {!detailLoading && detail && detail.top_invoices.length > 0 ? (
          <ul className="divide-y divide-border-default">
            {detail.top_invoices.map((inv) => (
              <li key={inv.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5">
                <div>
                  <Link
                    href={`/invoices/${inv.id}`}
                    className="text-sm font-semibold text-foreground hover:text-brand"
                  >
                    {inv.number}
                  </Link>
                  <p className="text-xs text-muted">
                    {inv.customer_name} · vade {formatDate(inv.due_date)}
                  </p>
                </div>
                <div className="text-right text-sm">
                  <p className="font-medium">{formatMoney(inv.open_amount, data.currency)}</p>
                  <p className="text-xs text-muted">
                    Beklenen {formatMoney(inv.expected_amount, data.currency)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
        <ChartInsight
          fallback={{
            what: "Seçili haftaya düşen en yüksek tutarlı açık faturalar.",
            why: "Haftalık nakit beklentisinin hangi carilerden geldiğini gösterir.",
            action: "Yüksek tutarlı ve düşük olasılıklı faturalar için arama görevi oluşturun.",
          }}
        />
      </section>
    </div>
  );
}

function actualPath(
  weeks: ForecastWeek[],
  point: (index: number, value: number) => { x: number; y: number },
) {
  const parts: string[] = [];
  let started = false;
  weeks.forEach((w, i) => {
    if (w.actual == null) {
      started = false;
      return;
    }
    const { x, y } = point(i, Number(w.actual) || 0);
    parts.push(`${started ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`);
    started = true;
  });
  return parts.join(" ");
}

function Legend({
  color,
  label,
  dashed,
  band,
}: {
  color: string;
  label: string;
  dashed?: boolean;
  band?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted">
      <span
        className={cn("inline-block", band ? "h-2.5 w-4 rounded-sm opacity-50" : "size-2.5 rounded-full")}
        style={{
          background: color,
          outline: dashed ? `1px dashed ${color}` : undefined,
        }}
      />
      {label}
    </span>
  );
}

function PanelRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="border-b border-border-default pb-2">
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="mt-0.5 font-serif text-xl tracking-tight text-foreground">{value}</dd>
    </div>
  );
}

function ForecastChart({
  weeks,
  selectedWeek,
  onSelectWeek,
  scenarioLine,
  currency,
}: {
  weeks: ForecastWeek[];
  selectedWeek: string | null;
  onSelectWeek: (weekStart: string) => void;
  scenarioLine: number[] | null;
  currency: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const width = 720;
  const height = 260;
  const padX = 36;
  const padY = 20;
  const plotW = width - padX * 2;
  const plotH = height - padY * 2;

  const maxVal = useMemo(() => {
    let m = 0;
    for (const w of weeks) {
      m = Math.max(
        m,
        Number(w.expected) || 0,
        Number(w.optimistic) || 0,
        Number(w.pessimistic) || 0,
        Number(w.actual) || 0,
      );
    }
    if (scenarioLine) {
      for (const v of scenarioLine) m = Math.max(m, v);
    }
    return m || 1;
  }, [weeks, scenarioLine]);

  const point = (index: number, value: number) => {
    const x = weeks.length === 1 ? width / 2 : padX + (index / (weeks.length - 1)) * plotW;
    const y = padY + (1 - value / maxVal) * plotH;
    return { x, y };
  };

  const pathFor = (values: number[]) =>
    values
      .map((v, i) => {
        const { x, y } = point(i, v);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");

  const bandPath = useMemo(() => {
    if (weeks.length === 0) return "";
    const top = weeks.map((w, i) => {
      const { x, y } = point(i, Number(w.optimistic) || 0);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    });
    const bottom = [...weeks]
      .reverse()
      .map((w, revI) => {
        const i = weeks.length - 1 - revI;
        const { x, y } = point(i, Number(w.pessimistic) || 0);
        return `L${x.toFixed(1)} ${y.toFixed(1)}`;
      });
    return `${top.join(" ")} ${bottom.join(" ")} Z`;
    // point depends on maxVal/weeks — intentional
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weeks, maxVal]);

  const hoverWeek = hover != null ? weeks[hover] : null;

  const summary = `13 haftalık nakit tahmini. En yüksek beklenen tahsilat ${Math.round(maxVal).toLocaleString("tr-TR")} seviyesinde. Grafik iyimser, beklenen ve kötümser senaryoları gösterir.`;

  return (
    <div className="relative">
      <p className="sr-only">{summary}</p>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-64 w-full"
        role="img"
        aria-label={summary}
        onMouseLeave={() => setHover(null)}
      >
        {[0.25, 0.5, 0.75].map((t) => (
          <line
            key={t}
            x1={padX}
            x2={width - padX}
            y1={padY + t * plotH}
            y2={padY + t * plotH}
            stroke="var(--color-border-default, #e2e8f0)"
            strokeWidth="1"
          />
        ))}
        <path d={bandPath} fill="rgba(15,118,110,0.10)" stroke="none" />
        <path
          d={pathFor(weeks.map((w) => Number(w.optimistic) || 0))}
          fill="none"
          stroke="#059669"
          strokeWidth="1.25"
          strokeDasharray="4 3"
          opacity={0.7}
        />
        <path
          d={pathFor(weeks.map((w) => Number(w.pessimistic) || 0))}
          fill="none"
          stroke="#b45309"
          strokeWidth="1.25"
          strokeDasharray="4 3"
          opacity={0.7}
        />
        <path
          d={pathFor(weeks.map((w) => Number(w.expected) || 0))}
          fill="none"
          stroke="#0f766e"
          strokeWidth="2.75"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <path
          d={actualPath(weeks, point)}
          fill="none"
          stroke="#334155"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {weeks.map((w, i) => {
          if (w.actual == null) return null;
          const { x, y } = point(i, Number(w.actual) || 0);
          return <circle key={`a-${w.week_start}`} cx={x} cy={y} r={3} fill="#334155" />;
        })}
        {scenarioLine ? (
          <path
            d={pathFor(scenarioLine)}
            fill="none"
            stroke="#0e7490"
            strokeWidth="2"
            strokeDasharray="6 4"
          />
        ) : null}
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
                fill={
                  selected
                    ? "rgba(15,118,110,0.10)"
                    : hover === i
                      ? "rgba(15,118,110,0.05)"
                      : "transparent"
                }
                className="cursor-pointer"
                onMouseEnter={() => setHover(i)}
                onClick={() => onSelectWeek(w.week_start)}
              />
              <circle
                cx={x}
                cy={point(i, Number(w.expected) || 0).y}
                r={selected ? 5 : 3.5}
                fill="#0f766e"
                className={cn("cursor-pointer", selected && "stroke-white stroke-2")}
                onMouseEnter={() => setHover(i)}
                onClick={() => onSelectWeek(w.week_start)}
              />
            </g>
          );
        })}
      </svg>
      {hoverWeek && hover != null ? (
        <div
          className="pointer-events-none absolute top-2 left-1/2 z-10 w-56 -translate-x-1/2 rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3 py-2 text-xs shadow-[var(--shadow-md)]"
        >
          <p className="font-semibold text-foreground">
            Hafta {formatDate(hoverWeek.week_start)}
          </p>
          <ul className="mt-1 space-y-0.5 text-muted">
            <li>Beklenen: {formatMoney(hoverWeek.expected, currency)}</li>
            <li>İyimser: {formatMoney(hoverWeek.optimistic, currency)}</li>
            <li>Kötümser: {formatMoney(hoverWeek.pessimistic, currency)}</li>
            <li>
              Gerçekleşen:{" "}
              {hoverWeek.actual != null ? formatMoney(hoverWeek.actual, currency) : "—"}
            </li>
          </ul>
        </div>
      ) : null}
    </div>
  );
}
