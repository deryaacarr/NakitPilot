import { apiRequest } from "@/lib/api/client";

import type { Invoice, InvoiceInput, InvoiceListParams, Paginated } from "./types";

export function listInvoices(params: InvoiceListParams = {}) {
  return apiRequest<Paginated<Invoice>>("/api/invoices/", { query: params });
}

export function getInvoice(id: number | string) {
  return apiRequest<Invoice>(`/api/invoices/${id}/`);
}

export function createInvoice(body: InvoiceInput) {
  return apiRequest<Invoice>("/api/invoices/", { method: "POST", body });
}

export function updateInvoice(id: number | string, body: Partial<InvoiceInput>) {
  return apiRequest<Invoice>(`/api/invoices/${id}/`, { method: "PATCH", body });
}

export function cancelInvoice(id: number | string) {
  return apiRequest<Invoice>(`/api/invoices/${id}/cancel/`, { method: "POST" });
}
