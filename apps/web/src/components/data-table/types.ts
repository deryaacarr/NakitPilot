import type { ReactNode } from "react";

import type { AppError } from "@/lib/errors";

export type SortDirection = "asc" | "desc";

export type DataTableSort = {
  id: string;
  direction: SortDirection;
};

export type DataTableColumn<T> = {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** Sıralanabilir kolon */
  sortable?: boolean;
  /** Kolon gizleme menüsünde göster (varsayılan: true) */
  hideable?: boolean;
  /** Başlangıçta gizli */
  defaultHidden?: boolean;
  className?: string;
};

export type DataTableFilterOption = {
  value: string;
  label: string;
};

export type DataTableFilter = {
  id: string;
  label: string;
  options: DataTableFilterOption[];
  /** Boş string = tümü */
  value: string;
};

export type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;

  /** Arama */
  search?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;

  /** Filtreler */
  filters?: DataTableFilter[];
  onFilterChange?: (filterId: string, value: string) => void;

  /** Sıralama */
  sort?: DataTableSort | null;
  onSortChange?: (sort: DataTableSort | null) => void;

  /** Pagination */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;

  /** Kolon görünürlüğü (kontrollü) */
  hiddenColumnIds?: string[];
  onHiddenColumnIdsChange?: (ids: string[]) => void;

  /** Durumlar */
  loading?: boolean;
  error?: AppError | string | null;
  onRetry?: () => void;

  emptyTitle?: string;
  emptyDescription?: string;
  emptyActionLabel?: string;
  onEmptyAction?: () => void;

  toolbarExtra?: ReactNode;
  className?: string;
};
