import { apiRequest } from "@/lib/api/client";

export type BulkAction =
  | "assign_tasks"
  | "change_assignee"
  | "add_tags"
  | "prepare_message"
  | "export_excel"
  | "recalculate_risk";

export type BulkResult = {
  action: string;
  selected: number;
  summary: string;
  created?: number;
  updated?: number;
  customers_updated?: number;
  customers?: number;
  customer_ids?: number[];
  href?: string;
  filename?: string;
  csv?: string;
  errors?: Array<{ invoice_id?: number; customer_id?: number; detail: string }>;
};

export function bulkInvoiceAction(
  action: BulkAction,
  invoiceIds: number[],
  extra: Record<string, unknown> = {},
) {
  return apiRequest<BulkResult>("/api/invoices/bulk/", {
    method: "POST",
    body: { action, invoice_ids: invoiceIds, ...extra },
  });
}
