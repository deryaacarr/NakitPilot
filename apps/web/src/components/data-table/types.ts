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
  /** Sticky first data column (NP-400) */
  sticky?: boolean;
  /** Text align for money columns */
  align?: "left" | "right";
  /** Initial width in px for resize */
  width?: number;
  /** Min width when resizing */
  minWidth?: number;
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

export type DataTableRowAction<T> = {
  id: string;
  label: string;
  onClick: (row: T) => void;
  tone?: "default" | "danger";
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

  /** Toplu seçim (NP-400 / NP-403) */
  selectable?: boolean;
  selectedKeys?: string[];
  onSelectedKeysChange?: (keys: string[]) => void;

  /** Satır tıklama / drawer (NP-404) */
  onRowClick?: (row: T) => void;
  activeRowKey?: string | null;

  /** Satır aksiyonları */
  rowActions?: DataTableRowAction<T>[] | ((row: T) => DataTableRowAction<T>[]);

  /** Sticky header + first column */
  stickyHeader?: boolean;
  stickyFirstColumn?: boolean;

  /** Durumlar */
  loading?: boolean;
  error?: AppError | string | null;
  onRetry?: () => void;

  emptyTitle?: string;
  emptyDescription?: string;
  /** NP-470 — why this empty state matters */
  emptyWhy?: string;
  emptyActionLabel?: string;
  onEmptyAction?: () => void;
  emptyActionHref?: string;

  /**
   * NP-482 — custom mobile card. When omitted, first visible columns are shown as labeled rows.
   * Desktop table stays unchanged; cards render below `md`.
   */
  mobileCard?: (row: T) => ReactNode;

  toolbarExtra?: ReactNode;
  /** Above table (e.g. bulk bar) */
  selectionBar?: ReactNode;
  className?: string;
  maxHeightClassName?: string;
};
