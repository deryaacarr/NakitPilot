import { apiRequest } from "@/lib/api/client";

export type PortalEndpointDoc = {
  method: string;
  path: string;
  summary: string;
  scope: string;
  headers?: Record<string, string>;
  request_example: Record<string, unknown> | null;
  response_example: Record<string, unknown>;
};

export type PortalDocs = {
  openapi_schema_url: string;
  openapi_docs_url: string;
  auth: {
    header: string;
    alternate_header: string;
    idempotency_header: string;
  };
  endpoints: PortalEndpointDoc[];
  webhook_events: Array<{ value: string; label: string }>;
  webhook_headers: string[];
};

export type UsagePoint = { date: string; total: number; errors: number };

export type UsageStats = {
  days: number;
  series: UsagePoint[];
  totals: { total: number; success: number; errors: number };
};

export type PortalError = {
  source: "api" | "webhook" | string;
  id: number;
  at: string;
  title: string;
  detail: string;
  status_code: number | null;
  api_key_prefix?: string;
  delivery_public_id?: string;
};

export function getDeveloperDocs() {
  return apiRequest<PortalDocs>("/api/developers/docs/");
}

export function getDeveloperUsage(days = 14) {
  return apiRequest<UsageStats>(`/api/developers/usage/?days=${days}`);
}

export function getDeveloperErrors(limit = 25) {
  return apiRequest<{ results: PortalError[] }>(`/api/developers/errors/?limit=${limit}`);
}
