"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { listCustomers } from "@/lib/customers/api";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { listInvoices } from "@/lib/invoices/api";
import { INVOICE_STATUS_LABELS, type Invoice, type InvoiceStatus } from "@/lib/invoices/types";
import type { AppError } from "@/lib/errors";

const STATUS_FILTERS = [
  { value: "OPEN", label: "Açık" },
  { value: "OVERDUE", label: "Gecikmiş" },
  { value: "PARTIALLY_PAID", label: "Kısmi ödenmiş" },
  { value: "PAID", label: "Ödenmiş" },
];

function statusTone(status: InvoiceStatus): "success" | "warning" | "danger" | "neutral" | "brand" {
  if (status === "PAID") return "success";
  if (status === "OPEN") return "brand";
  if (status === "PARTIALLY_PAID") return "warning";
  if (status === "OVERDUE") return "danger";
  return "neutral";
}

export function InvoiceListView() {
  const [rows, setRows] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [customer, setCustomer] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [amountMin, setAmountMin] = useState("");
  const [amountMax, setAmountMax] = useState("");
  const [overdueMin, setOverdueMin] = useState("");
  const [overdueMax, setOverdueMax] = useState("");
  const [sortId, setSortId] = useState<string | null>("invoice_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [customers, setCustomers] = useState<Array<{ id: number; name: string }>>([]);

  const pageSize = 20;

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      const result = await listCustomers({ page_size: 100, is_active: "true" });
      if (cancelled || !result.ok) return;
      setCustomers(result.data.results.map((c) => ({ id: c.id, name: c.name })));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const load = useCallback(async () => {
    const ordering = sortId == null ? "-invoice_date" : sortDir === "desc" ? `-${sortId}` : sortId;
    const result = await listInvoices({
      search: search || undefined,
      status: status || undefined,
      customer: customer || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      amount_min: amountMin || undefined,
      amount_max: amountMax || undefined,
      overdue_days_min: overdueMin || undefined,
      overdue_days_max: overdueMax || undefined,
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
  }, [
    search,
    status,
    customer,
    dateFrom,
    dateTo,
    amountMin,
    amountMax,
    overdueMin,
    overdueMax,
    sortId,
    sortDir,
    page,
  ]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      if (cancelled) return;
      setLoading(true);
      await load();
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const columns = useMemo<DataTableColumn<Invoice>[]>(
    () => [
      {
        id: "number",
        header: "Fatura numarası",
        sortable: true,
        cell: (row) => (
          <Link href={`/invoices/${row.id}`} className="text-brand font-medium hover:underline">
            {row.number}
          </Link>
        ),
      },
      {
        id: "customer",
        header: "Müşteri",
        cell: (row) => (
          <Link href={`/customers/${row.customer}`} className="hover:underline">
            {row.customer_name}
          </Link>
        ),
      },
      {
        id: "invoice_date",
        header: "Fatura tarihi",
        sortable: true,
        cell: (row) => formatDate(row.invoice_date),
      },
      {
        id: "due_date",
        header: "Vade tarihi",
        sortable: true,
        cell: (row) => formatDate(row.due_date),
      },
      {
        id: "total_amount",
        header: "Toplam",
        sortable: true,
        className: "text-right",
        cell: (row) => formatMoney(row.total_amount, row.currency),
      },
      {
        id: "allocated_amount",
        header: "Ödenen",
        className: "text-right",
        cell: (row) => formatMoney(row.allocated_amount, row.currency),
      },
      {
        id: "remaining_amount",
        header: "Kalan",
        className: "text-right",
        cell: (row) => formatMoney(row.remaining_amount, row.currency),
      },
      {
        id: "overdue_days",
        header: "Gecikme günü",
        cell: (row) =>
          row.status === "PAID"
            ? row.actual_delay_days == null
              ? "—"
              : `${row.actual_delay_days} gün`
            : `${row.overdue_days} gün`,
      },
      {
        id: "status",
        header: "Durum",
        sortable: true,
        cell: (row) => (
          <Badge tone={statusTone(row.status)}>{INVOICE_STATUS_LABELS[row.status]}</Badge>
        ),
      },
      {
        id: "assigned_user",
        header: "Sorumlu kişi",
        cell: (row) => row.assigned_user_name ?? "—",
      },
    ],
    [],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl tracking-tight text-slate-900">Faturalar</h1>
          <p className="mt-1 text-sm text-slate-600">Açık alacak ve gecikme takibi</p>
        </div>
        <Link
          href="/invoices/new"
          className="bg-brand text-brand-foreground inline-flex h-10 items-center justify-center rounded-lg px-4 text-sm font-semibold transition hover:bg-teal-800"
        >
          Yeni fatura
        </Link>
      </div>

      <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2 xl:grid-cols-4">
        <Input
          label="Tarih başlangıç"
          type="date"
          value={dateFrom}
          onChange={(e) => {
            setDateFrom(e.target.value);
            setPage(1);
          }}
        />
        <Input
          label="Tarih bitiş"
          type="date"
          value={dateTo}
          onChange={(e) => {
            setDateTo(e.target.value);
            setPage(1);
          }}
        />
        <Input
          label="Tutar min"
          value={amountMin}
          onChange={(e) => {
            setAmountMin(e.target.value);
            setPage(1);
          }}
          placeholder="0.00"
        />
        <Input
          label="Tutar max"
          value={amountMax}
          onChange={(e) => {
            setAmountMax(e.target.value);
            setPage(1);
          }}
          placeholder="0.00"
        />
        <Input
          label="Gecikme günü min"
          type="number"
          min={0}
          value={overdueMin}
          onChange={(e) => {
            setOverdueMin(e.target.value);
            setPage(1);
          }}
        />
        <Input
          label="Gecikme günü max"
          type="number"
          min={0}
          value={overdueMax}
          onChange={(e) => {
            setOverdueMax(e.target.value);
            setPage(1);
          }}
        />
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => String(row.id)}
        search={search}
        onSearchChange={(value) => {
          setSearch(value);
          setPage(1);
        }}
        searchPlaceholder="Fatura no, müşteri…"
        filters={[
          {
            id: "status",
            label: "Durum",
            value: status,
            options: STATUS_FILTERS,
          },
          {
            id: "customer",
            label: "Müşteri",
            value: customer,
            options: customers.map((c) => ({ value: String(c.id), label: c.name })),
          },
        ]}
        onFilterChange={(id, value) => {
          setPage(1);
          if (id === "status") setStatus(value);
          if (id === "customer") setCustomer(value);
        }}
        sort={sortId ? { id: sortId, direction: sortDir } : null}
        onSortChange={(next) => {
          setPage(1);
          if (!next) {
            setSortId("invoice_date");
            setSortDir("desc");
            return;
          }
          setSortId(next.id);
          setSortDir(next.direction);
        }}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        loading={loading}
        error={error}
        onRetry={() => void load()}
        emptyTitle="Fatura bulunamadı"
        emptyDescription="Filtreleri değiştirin veya yeni fatura ekleyin."
        emptyActionLabel="Yeni fatura"
        onEmptyAction={() => {
          window.location.href = "/invoices/new";
        }}
      />
    </div>
  );
}
