import { apiRequest } from "@/lib/api/client";

import type {
  FeatureFlag,
  ImpersonationStartResult,
  ImpersonationStatus,
  MaintenanceWindow,
  PlatformOverview,
  SupportTicket,
} from "./types";

export function fetchPlatformOverview(includeCustomerData = false) {
  return apiRequest<PlatformOverview>("/api/platform/overview/", {
    query: includeCustomerData ? { include_customer_data: true } : undefined,
  });
}

export function fetchFeatureFlags() {
  return apiRequest<{ results: FeatureFlag[]; known_keys: string[] }>(
    "/api/platform/feature-flags/",
  );
}

export function upsertFeatureFlag(body: Partial<FeatureFlag> & { key: string }) {
  return apiRequest<FeatureFlag>("/api/platform/feature-flags/", {
    method: "POST",
    body,
  });
}

export function evaluateFeatureFlags() {
  return apiRequest<{ flags: Record<string, boolean> }>("/api/platform/feature-flags/evaluate/");
}

export function fetchMaintenanceWindows() {
  return apiRequest<{ results: MaintenanceWindow[] }>("/api/platform/maintenance/");
}

export function createMaintenanceWindow(body: {
  scope: string;
  mode: string;
  organization_id?: number | null;
  module?: string;
  message?: string;
  ends_at?: string | null;
}) {
  return apiRequest<MaintenanceWindow>("/api/platform/maintenance/", {
    method: "POST",
    body,
  });
}

export function startImpersonation(body: {
  user_id: number;
  organization_id: number;
  reason: string;
  duration_minutes?: number;
  notify_target?: boolean;
}) {
  return apiRequest<ImpersonationStartResult>("/api/platform/impersonation/start/", {
    method: "POST",
    body,
  });
}

export function endImpersonation(sessionId?: string) {
  return apiRequest<{ ended: boolean }>("/api/platform/impersonation/end/", {
    method: "POST",
    body: sessionId ? { session_id: sessionId } : {},
  });
}

export function fetchImpersonationStatus() {
  return apiRequest<ImpersonationStatus>("/api/platform/impersonation/status/");
}

export function fetchSupportTickets() {
  return apiRequest<{ results: SupportTicket[] }>("/api/platform/support-tickets/");
}

export function createSupportTicket(body: {
  organization_id: number;
  subject: string;
  body?: string;
}) {
  return apiRequest<SupportTicket>("/api/platform/support-tickets/", {
    method: "POST",
    body,
  });
}
