export type InvoiceStatus = "DRAFT" | "OPEN" | "PARTIALLY_PAID" | "PAID" | "OVERDUE" | "CANCELLED";

export type Invoice = {
  id: number;
  organization: number;
  customer: number;
  customer_name: string;
  customer_code: string;
  number: string;
  invoice_date: string;
  due_date: string;
  currency: string;
  subtotal_amount: string;
  tax_amount: string;
  total_amount: string;
  remaining_amount: string;
  allocated_amount: string;
  overdue_days: number;
  actual_delay_days: number | null;
  delay_days_for_risk: number | null;
  status: InvoiceStatus;
  description: string;
  notes: string;
  assigned_user: number | null;
  assigned_user_name: string | null;
  payment_completion_date: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
  collection_outlook?: {
    probability_7d: string | null;
    probability_30d: string | null;
    probability_60d: string | null;
    expected_collection_date: string | null;
    expected_amount_7d?: string;
    expected_amount_30d?: string;
    expected_amount_60d?: string;
    overdue_days?: number;
    adjustments?: Array<{ code: string; label: string; delta: string }>;
  };
  payment_allocations?: Array<{
    id: number;
    amount: string;
    payment_id: number | null;
    payment_date: string | null;
  }>;
  collection_tasks?: unknown[];
  payment_promises?: unknown[];
  contact_history?: unknown[];
  audit_log?: unknown[];
};

export type InvoiceInput = {
  customer: number;
  number: string;
  invoice_date: string;
  due_date: string;
  currency?: string;
  subtotal_amount: string;
  tax_amount: string;
  total_amount: string;
  description?: string;
  notes?: string;
  assigned_user?: number | null;
  status?: InvoiceStatus;
};

export type InvoiceListParams = {
  search?: string;
  status?: string;
  customer?: string | number;
  date_from?: string;
  date_to?: string;
  invoice_date_from?: string;
  invoice_date_to?: string;
  due_date_from?: string;
  due_date_to?: string;
  amount_min?: string;
  amount_max?: string;
  overdue_days_min?: string;
  overdue_days_max?: string;
  ordering?: string;
  page?: number;
  page_size?: number;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  DRAFT: "Taslak",
  OPEN: "Açık",
  PARTIALLY_PAID: "Kısmi ödenmiş",
  PAID: "Ödenmiş",
  OVERDUE: "Gecikmiş",
  CANCELLED: "İptal",
};
