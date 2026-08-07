"use client";

import { useMemo, useState, type ReactNode } from "react";

import { ErrorState } from "@/components/errors/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { SkeletonBlock } from "@/components/ui/loading-skeleton";
import { Table } from "@/components/ui/table";
import { cn } from "@/lib/cn";

import { ColumnVisibilityMenu, SortIndicator } from "./column-visibility";
import type { DataTableColumn, DataTableProps } from "./types";

function headerLabel(header: ReactNode): string {
  if (typeof header === "string" || typeof header === "number") return String(header);
  return "Kolon";
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  search,
  onSearchChange,
  searchPlaceholder = "Ara…",
  filters = [],
  onFilterChange,
  sort = null,
  onSortChange,
  page,
  pageSize,
  total,
  onPageChange,
  hiddenColumnIds: controlledHidden,
  onHiddenColumnIdsChange,
  loading = false,
  error = null,
  onRetry,
  emptyTitle = "Kayıt bulunamadı",
  emptyDescription = "Arama veya filtreleri değiştirerek tekrar deneyin.",
  emptyActionLabel,
  onEmptyAction,
  toolbarExtra,
  className,
}: DataTableProps<T>) {
  const defaultHidden = useMemo(
    () => columns.filter((c) => c.defaultHidden).map((c) => c.id),
    [columns],
  );
  const [uncontrolledHidden, setUncontrolledHidden] = useState<string[]>(defaultHidden);

  const hiddenColumnIds = controlledHidden ?? uncontrolledHidden;
  const setHiddenColumnIds = onHiddenColumnIdsChange ?? setUncontrolledHidden;

  const visibleColumns = useMemo(
    () => columns.filter((column) => !hiddenColumnIds.includes(column.id)),
    [columns, hiddenColumnIds],
  );

  const tableColumns = useMemo(
    () =>
      visibleColumns.map((column) => ({
        key: column.id,
        header: <SortableHeader column={column} sort={sort} onSortChange={onSortChange} />,
        cell: column.cell,
        className: column.className,
      })),
    [visibleColumns, sort, onSortChange],
  );

  const showToolbar =
    Boolean(onSearchChange) ||
    filters.length > 0 ||
    Boolean(toolbarExtra) ||
    columns.some((c) => c.hideable !== false);

  return (
    <div className={cn("space-y-3", className)}>
      {showToolbar ? (
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-end">
            {onSearchChange ? (
              <div className="w-full sm:max-w-xs">
                <Input
                  label="Arama"
                  value={search ?? ""}
                  onChange={(event) => onSearchChange(event.target.value)}
                  placeholder={searchPlaceholder}
                />
              </div>
            ) : null}
            {filters.map((filter) => (
              <div key={filter.id} className="w-full sm:max-w-[12rem]">
                <Select
                  label={filter.label}
                  value={filter.value}
                  onChange={(event) => onFilterChange?.(filter.id, event.target.value)}
                  options={[{ value: "", label: "Tümü" }, ...filter.options]}
                />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2">
            {toolbarExtra}
            <ColumnVisibilityMenu
              columns={columns.map((c) => ({
                id: c.id,
                header: headerLabel(c.header),
                hideable: c.hideable,
              }))}
              hiddenColumnIds={hiddenColumnIds}
              onChange={setHiddenColumnIds}
            />
          </div>
        </div>
      ) : null}

      {error ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : loading ? (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-3/4" />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          title={emptyTitle}
          description={emptyDescription}
          actionLabel={emptyActionLabel}
          onAction={onEmptyAction}
        />
      ) : (
        <Table columns={tableColumns} rows={rows} rowKey={rowKey} />
      )}

      {!error && !loading ? (
        <Pagination page={page} pageSize={pageSize} total={total} onPageChange={onPageChange} />
      ) : null}
    </div>
  );
}

function SortableHeader<T>({
  column,
  sort,
  onSortChange,
}: {
  column: DataTableColumn<T>;
  sort: DataTableProps<T>["sort"];
  onSortChange: DataTableProps<T>["onSortChange"];
}) {
  if (!column.sortable || !onSortChange) {
    return <>{column.header}</>;
  }

  const active = sort?.id === column.id;

  return (
    <button
      type="button"
      className="inline-flex items-center font-semibold tracking-wide uppercase"
      onClick={() => {
        if (!active) {
          onSortChange({ id: column.id, direction: "asc" });
          return;
        }
        if (sort?.direction === "asc") {
          onSortChange({ id: column.id, direction: "desc" });
          return;
        }
        onSortChange(null);
      }}
    >
      {column.header}
      <SortIndicator active={Boolean(active)} direction={sort?.direction} />
    </button>
  );
}
