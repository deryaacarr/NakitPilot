import { apiRequest } from "@/lib/api/client";

import type { CollectionTask, CompleteTaskPayload, TimelineEvent, TodayBoard } from "./types";

export type CallPrepPayload = {
  customer_id: number;
  customer_name: string;
  customer_phone?: string;
  task_id: number | null;
  as_of: string;
  talking_points: string[];
  open_invoices: Array<{
    id: number;
    number: string;
    due_date: string;
    remaining_amount: string;
    overdue_days: number;
    status: string;
  }>;
  last_payment_promise: {
    id: number;
    amount: string;
    promised_date: string;
    status: string;
    notes: string;
  } | null;
  last_objection: {
    task_id: number;
    outcome: string;
    notes: string;
    completed_at: string | null;
  } | null;
  previous_call_notes: Array<{
    id: number;
    summary: string;
    notes: string;
    occurred_at: string;
    activity_type: string;
  }>;
  suggested_payment_plan: {
    label: string;
    installments: Array<{ amount: string; due_date: string }>;
    basis_open_balance: string;
  } | null;
  payment_plan_suggestions?: PaymentPlanSuggestions;
  open_balance: string;
  sources: Array<{
    type: string;
    id: number | null;
    label: string;
    field: string;
    value: string | number | null;
    url_hint?: string;
  }>;
};

export type PaymentPlanOptionId =
  | "UPFRONT_PLUS_INSTALLMENTS"
  | "WEEKLY"
  | "OLDEST_INVOICES_FIRST";

export type PaymentPlanStep = {
  amount: string;
  due_date: string;
  label: string;
  invoice_id: number | null;
  invoice_number: string | null;
};

export type PaymentPlanOption = {
  id: PaymentPlanOptionId;
  title: string;
  summary: string;
  steps: PaymentPlanStep[];
  total_amount: string;
  is_binding: boolean;
  requires_approval: boolean;
};

export type PaymentPlanSuggestions = {
  customer_id: number;
  customer_name: string;
  as_of: string;
  open_balance: string;
  payment_history: {
    payment_count: number;
    avg_payment: string;
    last_payment_date: string | null;
    last_payment_amount: string | null;
  };
  options: PaymentPlanOption[];
  is_binding: boolean;
  requires_approval: boolean;
  disclaimer: string;
};

export type StructuredNotesDraft = {
  promised_amount: string | null;
  promised_date: string | null;
  next_action_date: string | null;
  sentiment: string;
  objection: string | null;
};

export type ParseNotesResponse = {
  raw_notes: string;
  draft: StructuredNotesDraft;
  needs_confirm: boolean;
  as_of: string;
  confidence: Record<string, boolean>;
};

export function fetchTodayBoard() {
  return apiRequest<TodayBoard>("/api/collection-tasks/today/");
}

export function listCollectionTasks(query?: Record<string, string | number | boolean | null>) {
  return apiRequest<{ count: number; results: CollectionTask[] }>("/api/collection-tasks/", {
    query,
  });
}

export function completeCollectionTask(id: number, body: CompleteTaskPayload) {
  return apiRequest<{
    task: CollectionTask;
    follow_up: CollectionTask | null;
    promise_id: number | null;
  }>(`/api/collection-tasks/${id}/complete/`, {
    method: "POST",
    body,
  });
}

export function cancelCollectionTask(id: number, reason = "") {
  return apiRequest<CollectionTask>(`/api/collection-tasks/${id}/cancel/`, {
    method: "POST",
    body: { reason },
  });
}

export function bulkAssignTasks(taskIds: number[], assignedTo: number) {
  return apiRequest<{
    updated: number;
    assigned_to: number;
    warning?: string;
    warning_message?: string;
  }>("/api/collection-tasks/bulk-assign/", {
    method: "POST",
    body: { task_ids: taskIds, assigned_to: assignedTo },
  });
}

export function fetchCustomerTimeline(customerId: number, kinds?: string[]) {
  return apiRequest<{ results: TimelineEvent[] }>(`/api/customers/${customerId}/timeline/`, {
    query: kinds?.length ? { kinds: kinds.join(",") } : undefined,
  });
}

export function addCustomerTimelineNote(
  customerId: number,
  body: { notes: string; summary?: string },
) {
  return apiRequest<TimelineEvent>(`/api/customers/${customerId}/timeline/`, {
    method: "POST",
    body,
  });
}

export function fetchPrepareCall(taskId: number) {
  return apiRequest<CallPrepPayload>(`/api/collection-tasks/${taskId}/prepare-call/`);
}

export function parseCollectionNotes(taskId: number, rawNotes: string) {
  return apiRequest<ParseNotesResponse>(`/api/collection-tasks/${taskId}/parse-notes/`, {
    method: "POST",
    body: { raw_notes: rawNotes },
  });
}

export function confirmCollectionNotes(
  taskId: number,
  body: {
    raw_notes: string;
    promised_amount?: string | null;
    promised_date?: string | null;
    next_action_date?: string | null;
    sentiment?: string;
    objection?: string | null;
    complete_task?: boolean;
    confirmed: boolean;
  },
) {
  return apiRequest<{
    activity_id: number;
    promise_id: number | null;
    follow_up: CollectionTask | null;
    structured: StructuredNotesDraft & { confirmed?: boolean };
    completed: boolean;
    task: CollectionTask;
  }>(`/api/collection-tasks/${taskId}/confirm-notes/`, {
    method: "POST",
    body,
  });
}

export function fetchPaymentPlanSuggestions(customerId: number) {
  return apiRequest<PaymentPlanSuggestions>(
    `/api/customers/${customerId}/payment-plan-suggestions/`,
  );
}

export function acceptPaymentPlan(
  customerId: number,
  body: { option_id: PaymentPlanOptionId; confirmed: boolean },
) {
  return apiRequest<{
    accepted: boolean;
    option_id: PaymentPlanOptionId;
    option_title: string;
    promise_ids: number[];
    disclaimer: string;
    message: string;
  }>(`/api/customers/${customerId}/payment-plan-suggestions/accept/`, {
    method: "POST",
    body,
  });
}
