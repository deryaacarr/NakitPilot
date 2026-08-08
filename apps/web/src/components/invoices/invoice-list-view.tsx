"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { ListPage } from "@/components/templates";
import { Button, ButtonLink } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Money } from "@/components/ui/money";
import { StatusChip } from "@/components/ui/status-chip";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import { listCustomers } from "@/lib/customers/api";
import { formatDate } from "@/lib/customers/format";
import { RISK_LABELS, type RiskStatus } from "@/lib/customers/types";
import { listInvoices } from "@/lib/invoices/api";
import { INVOICE_STATUS_LABELS, type Invoice, type InvoiceStatus } from "@/lib/invoices/types";
import type { AppError } from "@/lib/errors";
import { EMPTY_PRESETS } from "@/lib/ui/empty-presets";
import {
  createSavedView,
  fetchSavedViewByToken,
  listSavedViews,
  normalizeSavedViews,
  setDefaultSavedView,
  type SavedTableView,
} from "@/lib/saved-views/api";
import type { SemanticTone } from "@/lib/design/semantic";

import { InvoiceBulkBar } from "./invoice-bulk-bar";
import { InvoiceDetailDrawer } from "./invoice-detail-drawer";

const STATUS_FILTERS = [
  { value: "OPEN", label: "Açık" },
  { value: "OVERDUE", label: "Gecikmiş" },
  { value: "PARTIALLY_PAID", label: "Kısmi ödenmiş" },
  { value: "PAID", label: "Ödenmiş" },
];

const PRESET_VIEWS: Array<{
  id: string;
  name: string;
  filters: Record<string, string>;
}> = [
  { id: "preset-90", name: "90+ gün gecikenler", filters: { status: "OVERDUE", overdue_days_min: "90" } },
  { id: "preset-mine", name: "Bana atanan müşteriler", filters: { assigned_user: "me" } },
  { id: "preset-250k", name: "250.000 TL üzeri açık bakiye", filters: { remaining_min: "250000", status: "OPEN,OVERDUE,PARTIALLY_PAID" } },
  { id: "preset-promise", name: "Bugün ödeme sözü olanlar", filters: { promise_today: "1" } },
  { id: "preset-critical", name: "Kritik riskli müşteriler", filters: { risk_status: "CRITICAL" } },
];

function statusTone(status: InvoiceStatus): SemanticTone {
  if (status === "PAID") return "success";
  if (status === "OPEN") return "info";
  if (status === "PARTIALLY_PAID") return "warning";
  if (status === "OVERDUE") return "danger";
  return "neutral";
}

function riskTone(status: string): SemanticTone {
  if (status === "LOW") return "success";
  if (status === "MEDIUM") return "warning";
  if (status === "HIGH" || status === "CRITICAL") return "danger";
  return "neutral";
}

type FilterState = {
  search: string;
  status: string;
  customer: string;
  assigned_user: string;
  risk_status: string;
  promise_today: string;
  remaining_min: string;
  date_from: string;
  date_to: string;
  amount_min: string;
  amount_max: string;
  overdue_days_min: string;
  overdue_days_max: string;
};

const EMPTY_FILTERS: FilterState = {
  search: "",
  status: "",
  customer: "",
  assigned_user: "",
  risk_status: "",
  promise_today: "",
  remaining_min: "",
  date_from: "",
  date_to: "",
  amount_min: "",
  amount_max: "",
  overdue_days_min: "",
  overdue_days_max: "",
};

export function InvoiceListView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const [rows, setRows] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [sortId, setSortId] = useState<string | null>("due_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [hiddenColumns, setHiddenColumns] = useState<string[]>(["invoice_date"]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [customers, setCustomers] = useState<Array<{ id: number; name: string }>>([]);
  const [assignees, setAssignees] = useState<Array<{ id: number; label: string }>>([]);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [drawerInvoice, setDrawerInvoice] = useState<Invoice | null>(null);
  const [savedViews, setSavedViews] = useState<SavedTableView[]>([]);
  const [activeViewId, setActiveViewId] = useState<string | null>(null);
  const [saveName, setSaveName] = useState("");
  const [shareView, setShareView] = useState(false);
  const [showSave, setShowSave] = useState(false);

  const pageSize = 20;

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [custRes, memRes] = await Promise.all([
        listCustomers({ page_size: 100, is_active: "true" }),
        apiRequest<Array<{ user_id: number; user_email: string; organization: number }>>(
          "/api/memberships/me/",
        ),
      ]);
      if (cancelled) return;
      if (custRes.ok) setCustomers(custRes.data.results.map((c) => ({ id: c.id, name: c.name })));
      if (memRes.ok) {
        const orgId = memRes.data[0]?.organization;
        if (orgId) {
          const orgMembers = await apiRequest<
            Array<{ user_id: number; user_email: string }> | { results: Array<{ user_id: number; user_email: string }> }
          >(`/api/organizations/${orgId}/memberships/`);
          if (orgMembers.ok) {
            const list = Array.isArray(orgMembers.data)
              ? orgMembers.data
              : orgMembers.data.results || [];
            setAssignees(list.map((m) => ({ id: m.user_id, label: m.user_email })));
          }
        }
      }
      const viewsRes = await listSavedViews("invoices");
      if (viewsRes.ok) {
        const views = normalizeSavedViews(viewsRes.data);
        setSavedViews(views);
        const def = views.find((v) => v.is_default);
        if (def && !searchParams.get("view") && !searchParams.get("view_token")) {
          applySavedView(def);
        }
      }
      const token = searchParams.get("view_token");
      if (token) {
        const byToken = await fetchSavedViewByToken(token);
        if (byToken.ok) applySavedView(byToken.data);
      }
      const viewId = searchParams.get("view");
      if (viewId && viewsRes.ok) {
        const found = normalizeSavedViews(viewsRes.data).find((v) => String(v.id) === viewId);
        if (found) applySavedView(found);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applySavedView(view: SavedTableView) {
    setActiveViewId(String(view.id));
    setFilters({ ...EMPTY_FILTERS, ...view.filters });
    if (view.hidden_columns?.length) setHiddenColumns(view.hidden_columns);
    if (view.sort?.id) {
      setSortId(view.sort.id);
      setSortDir(view.sort.direction === "desc" ? "desc" : "asc");
    }
    setPage(1);
  }

  function applyPreset(preset: (typeof PRESET_VIEWS)[number]) {
    setActiveViewId(preset.id);
    setFilters({ ...EMPTY_FILTERS, ...preset.filters });
    setPage(1);
  }

  const load = useCallback(async () => {
    const ordering = sortId == null ? "-due_date" : sortDir === "desc" ? `-${sortId}` : sortId;
    const result = await listInvoices({
      search: filters.search || undefined,
      status: filters.status || undefined,
      customer: filters.customer || undefined,
      assigned_user: filters.assigned_user || undefined,
      risk_status: filters.risk_status || undefined,
      promise_today: filters.promise_today || undefined,
      remaining_min: filters.remaining_min || undefined,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
      amount_min: filters.amount_min || undefined,
      amount_max: filters.amount_max || undefined,
      overdue_days_min: filters.overdue_days_min || undefined,
      overdue_days_max: filters.overdue_days_max || undefined,
      ordering,
      page,
      page_size: pageSize,
    });
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      setRows([]);
      setTotal(0);
      return;
    }
    setError(null);
    setRows(result.data.results);
    setTotal(result.data.count);
  }, [filters, sortId, sortDir, page]);

  useEffect(() => {
    setLoading(true);
    void load();
  }, [load]);

  const columns = useMemo<DataTableColumn<Invoice>[]>(
    () => [
      {
        id: "customer",
        header: "Müşteri",
        sticky: true,
        width: 180,
        cell: (row) => (
          <span className="block max-w-[11rem] truncate font-medium" title={row.customer_name}>
            {row.customer_name}
          </span>
        ),
      },
      {
        id: "number",
        header: "Fatura no",
        sortable: true,
        width: 130,
        cell: (row) => (
          <Link href={`/invoices/${row.id}`} className="font-medium text-primary hover:underline" onClick={(e) => e.stopPropagation()}>
            {row.number}
          </Link>
        ),
      },
      {
        id: "due_date",
        header: "Vade",
        sortable: true,
        cell: (row) => formatDate(row.due_date),
      },
      {
        id: "overdue_days",
        header: "Gecikme",
        cell: (row) => {
          const days = Math.max(row.overdue_days ?? 0, 0);
          if (row.status === "PAID") {
            return row.actual_delay_days == null ? "—" : `${Math.max(row.actual_delay_days, 0)}g`;
          }
          return days === 0 ? "—" : `${days}g`;
        },
      },
      {
        id: "total_amount",
        header: "Toplam",
        sortable: true,
        align: "right",
        cell: (row) => <Money value={row.total_amount} currency={row.currency} size="table" />,
      },
      {
        id: "remaining_amount",
        header: "Kalan",
        align: "right",
        cell: (row) => <Money value={row.remaining_amount} currency={row.currency} size="table" />,
      },
      {
        id: "risk",
        header: "Risk",
        cell: (row) => {
          const risk = (row.customer_risk_status || "MEDIUM") as RiskStatus;
          return <StatusChip tone={riskTone(risk)} label={RISK_LABELS[risk] ?? risk} />;
        },
      },
      {
        id: "assigned_user",
        header: "Sorumlu",
        cell: (row) => row.assigned_user_name ?? "—",
      },
      {
        id: "status",
        header: "Durum",
        sortable: true,
        cell: (row) => (
          <StatusChip tone={statusTone(row.status)} label={INVOICE_STATUS_LABELS[row.status]} />
        ),
      },
      {
        id: "invoice_date",
        header: "Fatura tarihi",
        sortable: true,
        defaultHidden: true,
        cell: (row) => formatDate(row.invoice_date),
      },
    ],
    [],
  );

  async function saveCurrentView() {
    if (!saveName.trim()) return;
    const res = await createSavedView({
      resource: "invoices",
      name: saveName.trim(),
      filters: Object.fromEntries(
        Object.entries(filters).filter(([, v]) => Boolean(v)),
      ) as Record<string, string>,
      hidden_columns: hiddenColumns,
      sort: sortId ? { id: sortId, direction: sortDir } : {},
      is_shared: shareView,
      is_default: false,
    });
    if (!res.ok) {
      toast({ title: "Görünüm kaydedilemedi", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Görünüm kaydedildi", tone: "success" });
    setShowSave(false);
    setSaveName("");
    const viewsRes = await listSavedViews("invoices");
    if (viewsRes.ok) {
      setSavedViews(normalizeSavedViews(viewsRes.data));
      setActiveViewId(String(res.data.id));
    }
  }

  async function copyViewLink(view: SavedTableView) {
    const url = view.is_shared && view.share_token
      ? `${window.location.origin}/invoices?view_token=${view.share_token}`
      : `${window.location.origin}/invoices?view=${view.id}`;
    await navigator.clipboard.writeText(url);
    toast({ title: "Görünüm linki kopyalandı", tone: "success" });
  }

  return (
    <ListPage
      title="Faturalar"
      description="Aksiyon odaklı alacak tablosu"
      actions={<ButtonLink href="/invoices/new">Yeni fatura</ButtonLink>}
      toolbar={
        <div className="flex w-full flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-subtle">
              Görünümler
            </span>
            {PRESET_VIEWS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => applyPreset(p)}
                className={[
                  "rounded-full border px-3 py-1 text-xs font-medium",
                  activeViewId === p.id
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border-default text-muted hover:bg-surface-tertiary",
                ].join(" ")}
              >
                {p.name}
              </button>
            ))}
            {savedViews.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => applySavedView(v)}
                className={[
                  "rounded-full border px-3 py-1 text-xs font-medium",
                  activeViewId === String(v.id)
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border-default text-muted hover:bg-surface-tertiary",
                ].join(" ")}
              >
                {v.name}
                {v.is_default ? " ★" : ""}
                {v.is_shared ? " ↗" : ""}
              </button>
            ))}
            <Button size="sm" variant="secondary" onClick={() => setShowSave(true)}>
              Görünümü kaydet
            </Button>
            {activeViewId && !activeViewId.startsWith("preset-") ? (
              <>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    const v = savedViews.find((x) => String(x.id) === activeViewId);
                    if (v)
                      void setDefaultSavedView(v.id).then(() =>
                        toast({ title: "Varsayılan görünüm ayarlandı", tone: "success" }),
                      );
                  }}
                >
                  Varsayılan yap
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    const v = savedViews.find((x) => String(x.id) === activeViewId);
                    if (v) void copyViewLink(v);
                  }}
                >
                  Linki kopyala
                </Button>
              </>
            ) : null}
          </div>
          {showSave ? (
            <div className="flex flex-wrap items-end gap-2 rounded-[var(--radius-lg)] border border-border-default bg-surface-secondary p-3">
              <Input
                label="Görünüm adı"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={shareView}
                  onChange={(e) => setShareView(e.target.checked)}
                />
                Ekiple paylaş
              </label>
              <Button size="sm" onClick={() => void saveCurrentView()}>
                Kaydet
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowSave(false)}>
                Vazgeç
              </Button>
            </div>
          ) : null}
          <div className="grid w-full gap-3 rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 md:grid-cols-2 xl:grid-cols-4">
            <Input
              label="Tarih başlangıç"
              type="date"
              value={filters.date_from}
              onChange={(e) => {
                setFilters((f) => ({ ...f, date_from: e.target.value }));
                setPage(1);
              }}
            />
            <Input
              label="Tarih bitiş"
              type="date"
              value={filters.date_to}
              onChange={(e) => {
                setFilters((f) => ({ ...f, date_to: e.target.value }));
                setPage(1);
              }}
            />
            <Input
              label="Kalan min"
              value={filters.remaining_min}
              onChange={(e) => {
                setFilters((f) => ({ ...f, remaining_min: e.target.value }));
                setPage(1);
              }}
              placeholder="250000"
            />
            <Input
              label="Gecikme günü min"
              type="number"
              min={0}
              value={filters.overdue_days_min}
              onChange={(e) => {
                setFilters((f) => ({ ...f, overdue_days_min: e.target.value }));
                setPage(1);
              }}
            />
          </div>
        </div>
      }
    >
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => String(row.id)}
        selectable
        selectedKeys={selectedKeys}
        onSelectedKeysChange={setSelectedKeys}
        stickyHeader
        stickyFirstColumn
        onRowClick={(row) => setDrawerInvoice(row)}
        activeRowKey={drawerInvoice ? String(drawerInvoice.id) : null}
        rowActions={(row) => [
          {
            id: "open",
            label: "Detay",
            onClick: () => setDrawerInvoice(row),
          },
          {
            id: "call",
            label: "Ara",
            onClick: () => {
              if (row.customer_phone) window.location.href = `tel:${row.customer_phone}`;
              else router.push(`/collections?customer=${row.customer}`);
            },
          },
          {
            id: "promise",
            label: "Söz",
            onClick: () => router.push(`/promises?create=1&customer=${row.customer}`),
          },
        ]}
        search={filters.search}
        onSearchChange={(value) => {
          setFilters((f) => ({ ...f, search: value }));
          setPage(1);
        }}
        searchPlaceholder="Fatura no, müşteri…"
        filters={[
          { id: "status", label: "Durum", value: filters.status, options: STATUS_FILTERS },
          {
            id: "customer",
            label: "Müşteri",
            value: filters.customer,
            options: customers.map((c) => ({ value: String(c.id), label: c.name })),
          },
          {
            id: "assigned_user",
            label: "Sorumlu",
            value: filters.assigned_user,
            options: [
              { value: "me", label: "Bana atanan" },
              ...assignees.map((a) => ({ value: String(a.id), label: a.label })),
            ],
          },
          {
            id: "risk_status",
            label: "Risk",
            value: filters.risk_status,
            options: [
              { value: "CRITICAL", label: "Kritik" },
              { value: "HIGH", label: "Yüksek" },
              { value: "MEDIUM", label: "Orta" },
              { value: "LOW", label: "Düşük" },
            ],
          },
        ]}
        onFilterChange={(id, value) => {
          setPage(1);
          setFilters((f) => ({ ...f, [id]: value }));
        }}
        sort={sortId ? { id: sortId, direction: sortDir } : null}
        onSortChange={(next) => {
          setPage(1);
          if (!next) {
            setSortId("due_date");
            setSortDir("asc");
            return;
          }
          setSortId(next.id);
          setSortDir(next.direction);
        }}
        hiddenColumnIds={hiddenColumns}
        onHiddenColumnIdsChange={setHiddenColumns}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        loading={loading}
        error={error}
        onRetry={() => void load()}
        emptyTitle={EMPTY_PRESETS.invoices.title}
        emptyDescription={EMPTY_PRESETS.invoices.description}
        emptyWhy={EMPTY_PRESETS.invoices.why}
        emptyActionLabel={EMPTY_PRESETS.invoices.actionLabel}
        emptyActionHref={EMPTY_PRESETS.invoices.actionHref}
        selectionBar={
          <InvoiceBulkBar
            selectedIds={selectedKeys.map(Number)}
            onClear={() => setSelectedKeys([])}
            onDone={() => {
              setSelectedKeys([]);
              void load();
            }}
            assignees={assignees}
          />
        }
      />

      <InvoiceDetailDrawer
        invoice={drawerInvoice}
        open={Boolean(drawerInvoice)}
        onClose={() => setDrawerInvoice(null)}
      />
    </ListPage>
  );
}
