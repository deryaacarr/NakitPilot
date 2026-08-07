import { apiRequest } from "@/lib/api/client";

import type { PaymentPromise, PromiseCalendar } from "./types";

export function fetchPromiseCalendar() {
  return apiRequest<PromiseCalendar>("/api/payment-promises/calendar/");
}

export function listPaymentPromises(query?: Record<string, string | number | boolean | null>) {
  return apiRequest<{ count: number; results: PaymentPromise[] }>("/api/payment-promises/", {
    query,
  });
}

export function createPaymentPromise(body: {
  customer: number;
  promised_date: string;
  amount: string;
  currency?: string;
  notes?: string;
  invoice?: number | null;
}) {
  return apiRequest<
    PaymentPromise | { promise: PaymentPromise; warnings: Record<string, unknown> }
  >("/api/payment-promises/", { method: "POST", body });
}

export function cancelPaymentPromise(id: number, reason = "") {
  return apiRequest<PaymentPromise>(`/api/payment-promises/${id}/cancel/`, {
    method: "POST",
    body: { reason },
  });
}

/** @deprecated Use `@/lib/notifications/api` */
export type { DashboardAlert } from "@/lib/notifications/api";
export {
  fetchDashboardAlerts,
  markAlertRead,
  markAllAlertsRead,
  normalizeAlertsPayload,
} from "@/lib/notifications/api";
