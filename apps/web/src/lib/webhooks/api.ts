import { apiRequest } from "@/lib/api/client";

import type { Paginated, WebhookDelivery } from "./types";

export type WebhookEndpoint = {
  id: number;
  name: string;
  url: string;
  description: string;
  secret_hint: string;
  is_active: boolean;
  consecutive_failures: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  created_at: string;
  updated_at: string;
  subscriptions: Array<{ id: number; event_type: string; is_active: boolean; created_at: string }>;
  secret?: string;
};

export function listWebhookDeliveries(status: "failed" | "all" | string = "failed") {
  const q = encodeURIComponent(status);
  return apiRequest<Paginated<WebhookDelivery> | WebhookDelivery[]>(
    `/api/webhooks/deliveries/?status=${q}`,
  );
}

export function resendWebhookDelivery(id: number | string) {
  return apiRequest<WebhookDelivery>(`/api/webhooks/deliveries/${id}/resend/`, {
    method: "POST",
  });
}

export function listWebhookEndpoints() {
  return apiRequest<Paginated<WebhookEndpoint> | WebhookEndpoint[]>("/api/webhooks/endpoints/");
}

export function createWebhookEndpoint(body: {
  name: string;
  url: string;
  description?: string;
  event_types?: string[];
}) {
  return apiRequest<WebhookEndpoint>("/api/webhooks/endpoints/", {
    method: "POST",
    body,
  });
}

export function testWebhookEndpoint(
  id: number | string,
  body: { event_type: string; payload?: Record<string, unknown> },
) {
  return apiRequest<{ deliveries: WebhookDelivery[] }>(`/api/webhooks/endpoints/${id}/test/`, {
    method: "POST",
    body,
  });
}
