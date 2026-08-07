import { apiRequest } from "@/lib/api/client";

export type CommunicationPreference = {
  id: number;
  customer_id: number;
  organization: number;
  email_ok: boolean;
  whatsapp_ok: boolean;
  sms_ok: boolean;
  phone_ok: boolean;
  no_contact_permission: boolean;
  contact_hours_start: string | null;
  contact_hours_end: string | null;
  notes: string;
  updated_at: string | null;
};

export type FrequencyCheck = {
  allowed: boolean;
  reason: string;
  code: string;
  auto_last_24h: number;
  messages_last_7d: number;
  open_dispute: boolean;
  limits: {
    max_auto_per_24h: number;
    max_messages_per_7d: number;
  };
};

export type Dispute = {
  id: number;
  customer: number;
  customer_name: string;
  invoice: number | null;
  invoice_number: string;
  category: string;
  category_label: string;
  status: string;
  status_label: string;
  amount: string | null;
  opened_at: string;
  description: string;
  resolution_note: string;
  resolved_at: string | null;
};

export type DisputeCategory = { value: string; label: string };

export function getCommunicationPreferences(customerId: number | string) {
  return apiRequest<CommunicationPreference>(
    `/api/customers/${customerId}/communication-preferences/`,
  );
}

export function updateCommunicationPreferences(
  customerId: number | string,
  body: Partial<CommunicationPreference>,
) {
  return apiRequest<CommunicationPreference>(
    `/api/customers/${customerId}/communication-preferences/`,
    { method: "PUT", body },
  );
}

export function getCommunicationFrequency(customerId: number | string) {
  return apiRequest<FrequencyCheck>(
    `/api/customers/${customerId}/communication-frequency/`,
  );
}

export function listDisputes(params: { customer_id?: number; open?: boolean } = {}) {
  return apiRequest<Dispute[] | { results: Dispute[] }>("/api/disputes/", {
    query: {
      customer_id: params.customer_id,
      open: params.open ? "true" : undefined,
    },
  });
}

export function listDisputeCategories() {
  return apiRequest<{ results: DisputeCategory[] }>("/api/disputes/categories/");
}

export function createDispute(body: {
  customer: number;
  invoice?: number | null;
  category: string;
  amount?: string;
  description?: string;
}) {
  return apiRequest<Dispute>("/api/disputes/", { method: "POST", body });
}

export function resolveDispute(
  id: number | string,
  body: { status?: string; resolution_note?: string },
) {
  return apiRequest<Dispute>(`/api/disputes/${id}/resolve/`, {
    method: "POST",
    body,
  });
}

export function transitionDispute(
  id: number | string,
  body: { status: string; note?: string; resolution_note?: string },
) {
  return apiRequest<Dispute>(`/api/disputes/${id}/transition/`, {
    method: "POST",
    body,
  });
}

export function getDisputeResolutionReport() {
  return apiRequest<{
    avg_resolution_hours: number | null;
    disputed_total_amount: string;
    resolved_total_amount: string;
    top_disputed_customers: Array<{
      customer_id: number;
      customer_name: string;
      dispute_count: number;
      total_amount: string;
    }>;
  }>("/api/disputes/resolution-report/");
}
