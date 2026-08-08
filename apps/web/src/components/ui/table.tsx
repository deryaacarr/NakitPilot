import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export type TableColumn<T> = {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
};

export type TableProps<T> = {
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  emptyMessage?: string;
  className?: string;
};

/** Simple presentational table (NP-500 tokens). Prefer DataTable for interactive lists. */
export function Table<T>({
  columns,
  rows,
  rowKey,
  emptyMessage = "Kayıt bulunamadı",
  className,
}: TableProps<T>) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-[var(--radius-lg)] border border-border-default bg-surface-primary",
        className,
      )}
    >
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-border-default bg-surface-secondary text-xs font-semibold tracking-wide text-subtle uppercase">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={cn("px-4 py-3", column.className)}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-sm text-muted">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={rowKey(row)} className="border-b border-border-default last:border-0">
                  {columns.map((column) => (
                    <td key={column.key} className={cn("px-4 py-3 text-foreground", column.className)}>
                      {column.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
