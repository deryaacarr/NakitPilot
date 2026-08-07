"use client";

import { useCallback, useMemo, useState } from "react";

import type { DataTableColumn, DataTableSort } from "./types";

export type UseDataTableStateOptions<T> = {
  columns: DataTableColumn<T>[];
  initialPageSize?: number;
  initialSort?: DataTableSort | null;
};

export function useDataTableState<T>(options: UseDataTableStateOptions<T>) {
  const { columns, initialPageSize = 20, initialSort = null } = options;

  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sort, setSort] = useState<DataTableSort | null>(initialSort);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(initialPageSize);

  const defaultHidden = useMemo(
    () => columns.filter((c) => c.defaultHidden).map((c) => c.id),
    [columns],
  );
  const [hiddenColumnIds, setHiddenColumnIds] = useState<string[]>(defaultHidden);

  const setFilter = useCallback((id: string, value: string) => {
    setFilters((current) => ({ ...current, [id]: value }));
    setPage(1);
  }, []);

  const setSearchAndResetPage = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const toggleSort = useCallback((columnId: string) => {
    setSort((current) => {
      if (!current || current.id !== columnId) {
        return { id: columnId, direction: "asc" };
      }
      if (current.direction === "asc") {
        return { id: columnId, direction: "desc" };
      }
      return null;
    });
  }, []);

  return {
    search,
    setSearch: setSearchAndResetPage,
    filters,
    setFilter,
    sort,
    setSort,
    toggleSort,
    page,
    setPage,
    pageSize,
    hiddenColumnIds,
    setHiddenColumnIds,
  };
}
