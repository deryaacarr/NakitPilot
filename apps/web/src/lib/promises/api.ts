import { apiRequest } from "@/lib/api/client";

import type { PaymentPromise, PromiseCalendar, PromiseStatusBoard } from "./types";

export type CreatePromiseBody = {
  customer: number;
  promised_date: string;
  amount: string;
  currency?: string;
  notes?: string;
  invoice?: number | null;
  create_follow_up?: boolean;
  assigned_to?: number | null;
  follow_up_due_date?: string | null;
};

export type CreatePromiseResult = {
  promise: PaymentPromise;
  warnings?: Record<string, unknown>;
  open_balance?: string;
  follow_up_task_id?: number;
};

export function fetchPromiseCalendar() {
  return apiRequest<PromiseCalendar>("/api/payment-promises/calendar/");
}

export function fetchPromiseStatusBoard() {
  return apiRequest<PromiseStatusBoard>("/api/payment-promises/board/");
}

export function listPaymentPromises(query?: Record<string, string | number | boolean | null>) {
  return apiRequest<{ count: number; results: PaymentPromise[] }>("/api/payment-promises/", {
    query,
  });
}

export function createPaymentPromise(body: CreatePromiseBody) {
  return apiRequest<PaymentPromise | CreatePromiseResult>("/api/payment-promises/", {
    method: "POST",
    body,
  });
}

export function normalizeCreatePromiseResponse(
  data: PaymentPromise | CreatePromiseResult,
): CreatePromiseResult {
  if ("promise" in data) return data;
  return { promise: data };
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
