"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { ListPage } from "@/components/templates";
import { ButtonLink } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/status-chip";
import { listCustomers } from "@/lib/customers/api";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { RISK_LABELS, type Customer, type RiskStatus } from "@/lib/customers/types";
import { apiRequest } from "@/lib/api/client";
import type { AppError } from "@/lib/errors";
import { EMPTY_PRESETS } from "@/lib/ui/empty-presets";
import type { SemanticTone } from "@/lib/design/semantic";

type MembershipRow = {
  user_id: number;
  user_email: string;
  organization: number;
};

const RISK_OPTIONS = (Object.keys(RISK_LABELS) as RiskStatus[]).map((value) => ({
  value,
  label: RISK_LABELS[value],
}));

function riskTone(status: RiskStatus): SemanticTone {
  if (status === "LOW") return "success";
  if (status === "MEDIUM") return "warning";
  if (status === "HIGH" || status === "CRITICAL") return "danger";
  return "neutral";
}

export function CustomerListView() {
  const [rows, setRows] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [riskStatus, setRiskStatus] = useState("");
  const [assignedUser, setAssignedUser] = useState("");
  const [city, setCity] = useState("");
  const [sector, setSector] = useState("");
  const [isActive, setIsActive] = useState("true");
  const [hasOverdue, setHasOverdue] = useState("");
  const [sortId, setSortId] = useState<string | null>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [assignees, setAssignees] = useState<MembershipRow[]>([]);
  const [cityOptions, setCityOptions] = useState<string[]>([]);
  const [sectorOptions, setSectorOptions] = useState<string[]>([]);

  const pageSize = 20;

  const loadMeta = useCallback(async () => {
    const memberships = await apiRequest<MembershipRow[]>("/api/memberships/me/");
    if (memberships.ok && memberships.data.length > 0) {
      const orgId = memberships.data[0].organization;
      const orgMembers = await apiRequest<MembershipRow[]>(
        `/api/organizations/${orgId}/memberships/`,
      );
      if (orgMembers.ok) {
        const list = Array.isArray(orgMembers.data)
          ? orgMembers.data
          : ((orgMembers.data as { results?: MembershipRow[] }).results ?? []);
        setAssignees(list);
      }
    }

    const facets = await listCustomers({ page_size: 100, is_active: "" });
    if (facets.ok) {
      const cities = [...new Set(facets.data.results.map((r) => r.city).filter(Boolean))].sort();
      const sectors = [...new Set(facets.data.results.map((r) => r.sector).filter(Boolean))].sort();
      setCityOptions(cities);
      setSectorOptions(sectors);
    }
  }, []);

  const load = useCallback(async () => {
    const ordering = sortId == null ? "name" : sortDir === "desc" ? `-${sortId}` : sortId;
    const result = await listCustomers({
      search: search || undefined,
      risk_status: riskStatus || undefined,
      assigned_user: assignedUser || undefined,
      city: city || undefined,
      sector: sector || undefined,
      is_active: isActive || undefined,
      has_overdue: hasOverdue || undefined,
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
  }, [search, riskStatus, assignedUser, city, sector, isActive, hasOverdue, sortId, sortDir, page]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      if (cancelled) return;
      await loadMeta();
    });
    return () => {
      cancelled = true;
    };
  }, [loadMeta]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      if (cancelled) return;
      setLoading(true);
      const ordering = sortId == null ? "name" : sortDir === "desc" ? `-${sortId}` : sortId;
      const result = await listCustomers({
        search: search || undefined,
        risk_status: riskStatus || undefined,
        assigned_user: assignedUser || undefined,
        city: city || undefined,
        sector: sector || undefined,
        is_active: isActive || undefined,
        has_overdue: hasOverdue || undefined,
        ordering,
        page,
        page_size: pageSize,
      });
      if (cancelled) return;
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
    });
    return () => {
      cancelled = true;
    };
  }, [search, riskStatus, assignedUser, city, sector, isActive, hasOverdue, sortId, sortDir, page]);

  const columns = useMemo<DataTableColumn<Customer>[]>(
    () => [
      {
        id: "code",
        header: "Müşteri kodu",
        sortable: true,
        cell: (row) => (
          <Link href={`/customers/${row.id}`} className="text-brand font-medium hover:underline">
            {row.code || "—"}
          </Link>
        ),
      },
      {
        id: "name",
        header: "Müşteri adı",
        sortable: true,
        cell: (row) => (
          <Link
            href={`/customers/${row.id}`}
            className="font-medium text-slate-900 hover:underline"
          >
            {row.name}
          </Link>
        ),
      },
      {
        id: "open_balance",
        header: "Toplam açık bakiye",
        cell: (row) => formatMoney(row.open_balance),
        className: "text-right",
      },
      {
        id: "overdue_balance",
        header: "Gecikmiş bakiye",
        cell: (row) => formatMoney(row.overdue_balance),
        className: "text-right",
      },
      {
        id: "avg_delay_days",
        header: "Ortalama gecikme",
        cell: (row) => (row.avg_delay_days == null ? "—" : `${row.avg_delay_days} gün`),
      },
      {
        id: "risk_status",
        header: "Risk seviyesi",
        sortable: true,
        cell: (row) => (
          <StatusChip tone={riskTone(row.risk_status)} label={RISK_LABELS[row.risk_status]} />
        ),
      },
      {
        id: "assigned_user",
        header: "Sorumlu kişi",
        cell: (row) => row.assigned_user_name ?? "—",
      },
      {
        id: "last_contact_at",
        header: "Son iletişim",
        sortable: true,
        cell: (row) => formatDate(row.last_contact_at),
      },
    ],
    [],
  );

  return (
    <ListPage
      title="Müşteriler"
      description="Cari hesap listesi ve risk görünümü"
      actions={<ButtonLink href="/customers/new">Yeni müşteri</ButtonLink>}
    >
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => String(row.id)}
        search={search}
        onSearchChange={(value) => {
          setSearch(value);
          setPage(1);
        }}
        searchPlaceholder="Kod, ad, vergi no, e-posta…"
        filters={[
          {
            id: "risk_status",
            label: "Risk seviyesi",
            value: riskStatus,
            options: RISK_OPTIONS,
          },
          {
            id: "assigned_user",
            label: "Sorumlu kullanıcı",
            value: assignedUser,
            options: assignees.map((m) => ({
              value: String(m.user_id),
              label: m.user_email,
            })),
          },
          {
            id: "city",
            label: "Şehir",
            value: city,
            options: cityOptions.map((c) => ({ value: c, label: c })),
          },
          {
            id: "sector",
            label: "Sektör",
            value: sector,
            options: sectorOptions.map((s) => ({ value: s, label: s })),
          },
          {
            id: "is_active",
            label: "Aktif/pasif",
            value: isActive,
            options: [
              { value: "true", label: "Aktif" },
              { value: "false", label: "Pasif" },
            ],
          },
          {
            id: "has_overdue",
            label: "Gecikmiş borcu olanlar",
            value: hasOverdue,
            options: [{ value: "true", label: "Yalnızca gecikmiş" }],
          },
        ]}
        onFilterChange={(id, value) => {
          setPage(1);
          if (id === "risk_status") setRiskStatus(value);
          if (id === "assigned_user") setAssignedUser(value);
          if (id === "city") setCity(value);
          if (id === "sector") setSector(value);
          if (id === "is_active") setIsActive(value);
          if (id === "has_overdue") setHasOverdue(value);
        }}
        sort={sortId ? { id: sortId, direction: sortDir } : null}
        onSortChange={(next) => {
          setPage(1);
          if (!next) {
            setSortId("name");
            setSortDir("asc");
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
        emptyTitle={EMPTY_PRESETS.customers.title}
        emptyDescription={EMPTY_PRESETS.customers.description}
        emptyWhy={EMPTY_PRESETS.customers.why}
        emptyActionLabel={EMPTY_PRESETS.customers.actionLabel}
        emptyActionHref={EMPTY_PRESETS.customers.actionHref}
      />
    </ListPage>
  );
}
