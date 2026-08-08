"use client";

import { useMemo, useState, type ReactNode } from "react";

import { ErrorState } from "@/components/errors/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { SkeletonBlock } from "@/components/ui/loading-skeleton";
import { cn } from "@/lib/cn";

import { ColumnVisibilityMenu, SortIndicator } from "./column-visibility";
import type { DataTableColumn, DataTableProps, DataTableRowAction } from "./types";

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
  selectable = false,
  selectedKeys = [],
  onSelectedKeysChange,
  onRowClick,
  activeRowKey = null,
  rowActions,
  stickyHeader = true,
  stickyFirstColumn = true,
  loading = false,
  error = null,
  onRetry,
  emptyTitle = "Kayıt bulunamadı",
  emptyDescription = "Arama veya filtreleri değiştirerek tekrar deneyin.",
  emptyActionLabel,
  onEmptyAction,
  toolbarExtra,
  selectionBar,
  className,
  maxHeightClassName = "max-h-[min(36rem,70vh)]",
}: DataTableProps<T>) {
  const defaultHidden = useMemo(
    () => columns.filter((c) => c.defaultHidden).map((c) => c.id),
    [columns],
  );
  const [uncontrolledHidden, setUncontrolledHidden] = useState<string[]>(defaultHidden);
  const [widths, setWidths] = useState<Record<string, number>>(() => {
    const init: Record<string, number> = {};
    for (const c of columns) {
      if (c.width) init[c.id] = c.width;
    }
    return init;
  });

  const hiddenColumnIds = controlledHidden ?? uncontrolledHidden;
  const setHiddenColumnIds = onHiddenColumnIdsChange ?? setUncontrolledHidden;

  const visibleColumns = useMemo(
    () => columns.filter((column) => !hiddenColumnIds.includes(column.id)),
    [columns, hiddenColumnIds],
  );

  const firstStickyId = stickyFirstColumn
    ? visibleColumns.find((c) => c.sticky !== false)?.id
    : null;

  const rowKeys = rows.map((r) => rowKey(r));
  const allSelected = rowKeys.length > 0 && rowKeys.every((k) => selectedKeys.includes(k));
  const someSelected = selectedKeys.length > 0 && !allSelected;

  function toggleAll() {
    if (!onSelectedKeysChange) return;
    onSelectedKeysChange(allSelected ? [] : rowKeys);
  }

  function toggleOne(key: string) {
    if (!onSelectedKeysChange) return;
    if (selectedKeys.includes(key)) {
      onSelectedKeysChange(selectedKeys.filter((k) => k !== key));
    } else {
      onSelectedKeysChange([...selectedKeys, key]);
    }
  }

  function resolveActions(row: T): DataTableRowAction<T>[] {
    if (!rowActions) return [];
    return typeof rowActions === "function" ? rowActions(row) : rowActions;
  }

  function startResize(columnId: string, startX: number, startW: number, minW: number) {
    const onMove = (event: MouseEvent) => {
      const next = Math.max(minW, startW + (event.clientX - startX));
      setWidths((prev) => ({ ...prev, [columnId]: next }));
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  const showToolbar =
    Boolean(onSearchChange) ||
    filters.length > 0 ||
    Boolean(toolbarExtra) ||
    columns.some((c) => c.hideable !== false);

  return (
    <div className={cn("space-y-3", className)}>
      {showToolbar ? (
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
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

      {selectionBar}

      {error ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : loading ? (
        <div className="space-y-2 rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
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
        <div className="overflow-hidden rounded-[var(--radius-lg)] border border-border-default bg-surface-primary">
          <div className={cn("overflow-auto", maxHeightClassName)}>
            <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
              <thead
                className={cn(
                  "bg-surface-secondary text-xs font-semibold tracking-wide text-subtle uppercase",
                  stickyHeader && "sticky top-0 z-20",
                )}
              >
                <tr>
                  {selectable ? (
                    <th
                      className={cn(
                        "w-10 border-b border-border-default bg-surface-secondary px-3 py-3",
                        stickyHeader && "sticky top-0 z-30",
                        stickyFirstColumn && "sticky left-0 z-40",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={allSelected}
                        ref={(el) => {
                          if (el) el.indeterminate = someSelected;
                        }}
                        onChange={toggleAll}
                        aria-label="Tümünü seç"
                      />
                    </th>
                  ) : null}
                  {visibleColumns.map((column) => {
                    const isSticky = column.id === firstStickyId;
                    const w = widths[column.id] ?? column.width;
                    return (
                      <th
                        key={column.id}
                        style={w ? { width: w, minWidth: w } : undefined}
                        className={cn(
                          "relative border-b border-border-default bg-surface-secondary px-4 py-3",
                          column.align === "right" && "text-right",
                          column.className,
                          stickyHeader && "sticky top-0 z-20",
                          isSticky && "sticky left-0 z-30 shadow-[1px_0_0_var(--border-default)]",
                          selectable && isSticky && "left-10",
                        )}
                      >
                        <SortableHeader column={column} sort={sort} onSortChange={onSortChange} />
                        <button
                          type="button"
                          aria-label={`${headerLabel(column.header)} genişliğini ayarla`}
                          className="absolute top-0 right-0 h-full w-1 cursor-col-resize hover:bg-primary/40"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            const startW = w ?? e.currentTarget.parentElement?.offsetWidth ?? 120;
                            startResize(column.id, e.clientX, startW, column.minWidth ?? 72);
                          }}
                        />
                      </th>
                    );
                  })}
                  {rowActions ? (
                    <th className="sticky top-0 z-20 border-b border-border-default bg-surface-secondary px-4 py-3">
                      Aksiyon
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const key = rowKey(row);
                  const selected = selectedKeys.includes(key);
                  const active = activeRowKey === key;
                  const actions = resolveActions(row);
                  return (
                    <tr
                      key={key}
                      className={cn(
                        "border-b border-border-default last:border-0",
                        selected && "bg-primary/5",
                        active && "bg-primary/10",
                        onRowClick && "cursor-pointer hover:bg-surface-secondary/80",
                      )}
                      onClick={() => onRowClick?.(row)}
                    >
                      {selectable ? (
                        <td
                          className={cn(
                            "bg-surface-primary px-3 py-3",
                            stickyFirstColumn && "sticky left-0 z-10",
                            selected && "bg-primary/5",
                          )}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleOne(key)}
                            aria-label="Satırı seç"
                          />
                        </td>
                      ) : null}
                      {visibleColumns.map((column) => {
                        const isSticky = column.id === firstStickyId;
                        const w = widths[column.id] ?? column.width;
                        return (
                          <td
                            key={column.id}
                            style={w ? { width: w, minWidth: w } : undefined}
                            className={cn(
                              "bg-surface-primary px-4 py-3 text-foreground",
                              column.align === "right" && "text-right tabular-nums",
                              column.className,
                              isSticky &&
                                "sticky left-0 z-10 shadow-[1px_0_0_var(--border-default)]",
                              selectable && isSticky && "left-10",
                              (selected || active) && "bg-primary/5",
                            )}
                          >
                            {column.cell(row)}
                          </td>
                        );
                      })}
                      {rowActions ? (
                        <td
                          className="px-4 py-3"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div className="flex flex-wrap gap-1">
                            {actions.map((action) => (
                              <button
                                key={action.id}
                                type="button"
                                className={cn(
                                  "rounded-[var(--radius-md)] border border-border-default px-2 py-1 text-xs font-semibold",
                                  action.tone === "danger" && "border-danger/40 text-danger",
                                )}
                                onClick={() => action.onClick(row)}
                              >
                                {action.label}
                              </button>
                            ))}
                          </div>
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
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
