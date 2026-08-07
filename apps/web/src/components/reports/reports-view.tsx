"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { ErrorState } from "@/components/errors";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { listCustomers } from "@/lib/customers/api";
import type { Customer } from "@/lib/customers/types";
import type { AppError } from "@/lib/errors";
import { cn } from "@/lib/cn";
import {
  createReportExport,
  downloadExportJob,
  fetchReportPreview,
  type ActivityRow,
  type OverdueRow,
  type ReportType,
  type RiskRow,
} from "@/lib/reports/api";

const TABS: { id: ReportType; label: string; description: string }[] = [
  {
    id: "OVERDUE_RECEIVABLES",
    label: "Gecikmiş alacak",
    description: "Vadesi geçmiş açık faturalar",
  },
  {
    id: "COLLECTION_ACTIVITY",
    label: "Tahsilat aktivite",
    description: "Kullanıcı bazında tahsilat performansı",
  },
  {
    id: "CUSTOMER_RISK",
    label: "Müşteri risk",
    description: "Risk skoru ve nedenleri",
  },
];

const RISK_OPTIONS = [
  { value: "", label: "Tüm riskler" },
  { value: "LOW", label: "Düşük" },
  { value: "MEDIUM", label: "Orta" },
  { value: "HIGH", label: "Yüksek" },
  { value: "CRITICAL", label: "Kritik" },
];

const PRESET_OPTIONS = [
  { value: "today", label: "Bugün" },
  { value: "week", label: "Bu hafta" },
  { value: "month", label: "Bu ay" },
  { value: "last_30", label: "Son 30 gün" },
  { value: "custom", label: "Özel" },
];

type Filters = {
  date_from: string;
  date_to: string;
  customer: string;
  risk_status: string;
  assigned_user: string;
  overdue_days_min: string;
  overdue_days_max: string;
  preset: string;
};

const EMPTY_FILTERS: Filters = {
  date_from: "",
  date_to: "",
  customer: "",
  risk_status: "",
  assigned_user: "",
  overdue_days_min: "",
  overdue_days_max: "",
  preset: "month",
};

export function ReportsView() {
  const { toast } = useToast();
  const [tab, setTab] = useState<ReportType>("OVERDUE_RECEIVABLES");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [rows, setRows] = useState<OverdueRow[] | ActivityRow[] | RiskRow[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<AppError | null>(null);

  useEffect(() => {
    void listCustomers({ page_size: 100, is_active: "true" }).then((res) => {
      if (res.ok) setCustomers(res.data.results);
    });
  }, []);

  const query = useMemo(() => {
    const q: Record<string, string> = {};
    if (tab === "OVERDUE_RECEIVABLES") {
      if (filters.date_from) q.date_from = filters.date_from;
      if (filters.date_to) q.date_to = filters.date_to;
      if (filters.customer) q.customer = filters.customer;
      if (filters.risk_status) q.risk_status = filters.risk_status;
      if (filters.assigned_user) q.assigned_user = filters.assigned_user;
      if (filters.overdue_days_min) q.overdue_days_min = filters.overdue_days_min;
      if (filters.overdue_days_max) q.overdue_days_max = filters.overdue_days_max;
    } else if (tab === "COLLECTION_ACTIVITY") {
      q.preset = filters.preset;
      if (filters.preset === "custom") {
        if (filters.date_from) q.date_from = filters.date_from;
        if (filters.date_to) q.date_to = filters.date_to;
      }
    } else {
      if (filters.risk_status) q.risk_status = filters.risk_status;
      if (filters.assigned_user) q.assigned_user = filters.assigned_user;
    }
    return q;
  }, [tab, filters]);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchReportPreview(tab, query);
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError(null);
    setCount(result.data.count);
    setRows(result.data.results as OverdueRow[] | ActivityRow[] | RiskRow[]);
  }, [tab, query]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onExport() {
    setExporting(true);
    const result = await createReportExport(tab, query);
    if (!result.ok) {
      setExporting(false);
      toast({ title: "Dışa aktarma başarısız", description: result.error.message, tone: "error" });
      return;
    }
    if (result.data.status === "READY") {
      const dl = await downloadExportJob(result.data.id);
      setExporting(false);
      if (!dl.ok) {
        toast({ title: "İndirme hatası", description: dl.detail, tone: "error" });
        return;
      }
      toast({ title: "Excel indirildi", description: `${result.data.row_count} satır`, tone: "success" });
      return;
    }
    setExporting(false);
    toast({
      title: "Rapor hazırlanıyor",
      description: "Durum: " + result.data.status_label,
      tone: "default",
    });
  }

  function setFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Raporlar</h1>
        <p className="mt-1 text-sm text-slate-600">
          Gecikmiş alacak, tahsilat aktivite ve müşteri risk raporları
        </p>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              setTab(item.id);
              setFilters(EMPTY_FILTERS);
            }}
            className={cn(
              "rounded-lg px-3 py-2 text-left text-sm transition",
              tab === item.id
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200",
            )}
          >
            <span className="block font-medium">{item.label}</span>
            <span className={cn("block text-xs", tab === item.id ? "text-slate-300" : "text-slate-500")}>
              {item.description}
            </span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        {tab === "OVERDUE_RECEIVABLES" ? (
          <>
            <Field label="Vade başlangıç">
              <Input
                type="date"
                value={filters.date_from}
                onChange={(e) => setFilter("date_from", e.target.value)}
              />
            </Field>
            <Field label="Vade bitiş">
              <Input
                type="date"
                value={filters.date_to}
                onChange={(e) => setFilter("date_to", e.target.value)}
              />
            </Field>
            <Field label="Müşteri">
              <select
                className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"
                value={filters.customer}
                onChange={(e) => setFilter("customer", e.target.value)}
              >
                <option value="">Tümü</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Risk">
              <select
                className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"
                value={filters.risk_status}
                onChange={(e) => setFilter("risk_status", e.target.value)}
              >
                {RISK_OPTIONS.map((o) => (
                  <option key={o.value || "all"} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Gecikme min">
              <Input
                type="number"
                min={0}
                placeholder="1"
                value={filters.overdue_days_min}
                onChange={(e) => setFilter("overdue_days_min", e.target.value)}
              />
            </Field>
            <Field label="Gecikme max">
              <Input
                type="number"
                min={0}
                placeholder="—"
                value={filters.overdue_days_max}
                onChange={(e) => setFilter("overdue_days_max", e.target.value)}
              />
            </Field>
          </>
        ) : null}

        {tab === "COLLECTION_ACTIVITY" ? (
          <>
            <Field label="Dönem">
              <select
                className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"
                value={filters.preset}
                onChange={(e) => setFilter("preset", e.target.value)}
              >
                {PRESET_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>
            {filters.preset === "custom" ? (
              <>
                <Field label="Başlangıç">
                  <Input
                    type="date"
                    value={filters.date_from}
                    onChange={(e) => setFilter("date_from", e.target.value)}
                  />
                </Field>
                <Field label="Bitiş">
                  <Input
                    type="date"
                    value={filters.date_to}
                    onChange={(e) => setFilter("date_to", e.target.value)}
                  />
                </Field>
              </>
            ) : null}
          </>
        ) : null}

        {tab === "CUSTOMER_RISK" ? (
          <Field label="Risk">
            <select
              className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"
              value={filters.risk_status}
              onChange={(e) => setFilter("risk_status", e.target.value)}
            >
              {RISK_OPTIONS.map((o) => (
                <option key={o.value || "all"} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
        ) : null}

        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          Yenile
        </Button>
        <Button onClick={() => void onExport()} loading={exporting}>
          Excel’e aktar
        </Button>
      </div>

      {error ? <ErrorState error={error} onRetry={() => void load()} /> : null}

      {loading && !error ? <LoadingSkeleton lines={8} /> : null}

      {!loading && !error && rows.length === 0 ? (
        <EmptyState title="Kayıt yok" description="Filtrelere uygun rapor satırı bulunamadı." />
      ) : null}

      {!loading && !error && rows.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs text-slate-500">{count} satır (önizleme en fazla 500)</p>
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            {tab === "OVERDUE_RECEIVABLES" ? <OverdueTable rows={rows as OverdueRow[]} /> : null}
            {tab === "COLLECTION_ACTIVITY" ? <ActivityTable rows={rows as ActivityRow[]} /> : null}
            {tab === "CUSTOMER_RISK" ? <RiskTable rows={rows as RiskRow[]} /> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
      {label}
      {children}
    </label>
  );
}

function OverdueTable({ rows }: { rows: OverdueRow[] }) {
  return (
    <table className="min-w-full text-left text-sm">
      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
        <tr>
          <th className="px-3 py-2">Müşteri</th>
          <th className="px-3 py-2">Fatura</th>
          <th className="px-3 py-2">Açık bakiye</th>
          <th className="px-3 py-2">Vade</th>
          <th className="px-3 py-2">Gecikme</th>
          <th className="px-3 py-2">Risk</th>
          <th className="px-3 py-2">Son iletişim</th>
          <th className="px-3 py-2">Ödeme sözü</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={`${r.invoice_number}-${i}`} className="border-t border-slate-100">
            <td className="px-3 py-2 font-medium text-slate-900">{r.customer_name}</td>
            <td className="px-3 py-2 text-slate-700">{r.invoice_number}</td>
            <td className="px-3 py-2 tabular-nums">{r.open_balance}</td>
            <td className="px-3 py-2">{r.due_date}</td>
            <td className="px-3 py-2 tabular-nums">{r.overdue_days}</td>
            <td className="px-3 py-2">
              {r.risk_status} ({r.risk_score})
            </td>
            <td className="px-3 py-2 text-slate-600">{r.last_contact_at || "—"}</td>
            <td className="px-3 py-2 text-slate-600">{r.payment_promise || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ActivityTable({ rows }: { rows: ActivityRow[] }) {
  return (
    <table className="min-w-full text-left text-sm">
      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
        <tr>
          <th className="px-3 py-2">Kullanıcı</th>
          <th className="px-3 py-2">Görev</th>
          <th className="px-3 py-2">Görüşme</th>
          <th className="px-3 py-2">Alınan söz</th>
          <th className="px-3 py-2">Tutulan</th>
          <th className="px-3 py-2">Bozulan</th>
          <th className="px-3 py-2">Tahsilat</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.user_id ?? r.user_email} className="border-t border-slate-100">
            <td className="px-3 py-2">
              <div className="font-medium text-slate-900">{r.user_name}</div>
              <div className="text-xs text-slate-500">{r.user_email}</div>
            </td>
            <td className="px-3 py-2 tabular-nums">{r.tasks_completed}</td>
            <td className="px-3 py-2 tabular-nums">{r.contacts_made}</td>
            <td className="px-3 py-2 tabular-nums">{r.promises_taken}</td>
            <td className="px-3 py-2 tabular-nums">{r.promises_kept}</td>
            <td className="px-3 py-2 tabular-nums">{r.promises_broken}</td>
            <td className="px-3 py-2 tabular-nums">{r.collected_amount}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RiskTable({ rows }: { rows: RiskRow[] }) {
  return (
    <table className="min-w-full text-left text-sm">
      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
        <tr>
          <th className="px-3 py-2">Müşteri</th>
          <th className="px-3 py-2">Skor</th>
          <th className="px-3 py-2">Seviye</th>
          <th className="px-3 py-2">Nedenler</th>
          <th className="px-3 py-2">Gecikmiş bakiye</th>
          <th className="px-3 py-2">Ort. gecikme</th>
          <th className="px-3 py-2">Bozulan söz</th>
          <th className="px-3 py-2">Son ödeme</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.customer_code} className="border-t border-slate-100">
            <td className="px-3 py-2">
              <div className="font-medium text-slate-900">{r.customer_name}</div>
              <div className="text-xs text-slate-500">{r.customer_code}</div>
            </td>
            <td className="px-3 py-2 tabular-nums">{r.risk_score}</td>
            <td className="px-3 py-2">{r.risk_status}</td>
            <td className="max-w-xs px-3 py-2 text-slate-600">{r.risk_reasons || "—"}</td>
            <td className="px-3 py-2 tabular-nums">{r.overdue_balance}</td>
            <td className="px-3 py-2 tabular-nums">
              {r.avg_delay_days != null ? r.avg_delay_days : "—"}
            </td>
            <td className="px-3 py-2 tabular-nums">{r.broken_promise_count}</td>
            <td className="px-3 py-2">{r.last_payment_date || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
