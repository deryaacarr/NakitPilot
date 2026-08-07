import { apiRequest } from "@/lib/api/client";

import type {
  CompanyOption,
  CredentialStatus,
  IntegrationConnection,
  IntegrationMonitoring,
  IntegrationProvider,
  Paginated,
  SyncConflict,
  SyncConflictResolution,
  SyncFrequency,
  SyncJob,
} from "./types";

export function listProviders() {
  return apiRequest<IntegrationProvider[]>("/api/integrations/providers/");
}

export function listConnections() {
  return apiRequest<Paginated<IntegrationConnection> | IntegrationConnection[]>(
    "/api/integrations/connections/",
  );
}

export function getConnection(id: number | string) {
  return apiRequest<IntegrationConnection>(`/api/integrations/connections/${id}/`);
}

export function createConnection(body: {
  provider: string;
  external_company_id?: string;
  external_company_name?: string;
}) {
  return apiRequest<IntegrationConnection>("/api/integrations/connections/", {
    method: "POST",
    body,
  });
}

export function putCredentials(
  connectionId: number | string,
  credentials: Record<string, string>,
) {
  return apiRequest<CredentialStatus>(
    `/api/integrations/connections/${connectionId}/credentials/`,
    { method: "PUT", body: { credentials } },
  );
}

export function testConnection(connectionId: number | string) {
  return apiRequest<{ result: { ok: boolean; message?: string }; connection: IntegrationConnection }>(
    `/api/integrations/connections/${connectionId}/test/`,
    { method: "POST" },
  );
}

export function listCompanies(connectionId: number | string) {
  return apiRequest<CompanyOption[]>(`/api/integrations/connections/${connectionId}/companies/`);
}

export function selectCompany(
  connectionId: number | string,
  body: { external_company_id: string; external_company_name?: string },
) {
  return apiRequest<IntegrationConnection>(
    `/api/integrations/connections/${connectionId}/select-company/`,
    { method: "POST", body },
  );
}

export function updateSyncSettings(
  connectionId: number | string,
  body: { sync_frequency: SyncFrequency; settings_json?: Record<string, unknown> },
) {
  return apiRequest<IntegrationConnection>(
    `/api/integrations/connections/${connectionId}/sync-settings/`,
    { method: "PATCH", body },
  );
}

export function startSync(
  connectionId: number | string,
  jobType: "initial" | "manual" | "full" = "manual",
) {
  return apiRequest<{ job: SyncJob; connection: IntegrationConnection }>(
    `/api/integrations/connections/${connectionId}/sync/`,
    { method: "POST", body: { job_type: jobType } },
  );
}

export function getMonitoring(connectionId: number | string) {
  return apiRequest<IntegrationMonitoring>(
    `/api/integrations/connections/${connectionId}/monitoring/`,
  );
}

export function listConflicts(
  connectionId: number | string,
  status: "open" | "resolved" | "all" = "open",
) {
  const q = status === "all" ? "all" : status;
  return apiRequest<SyncConflict[]>(
    `/api/integrations/connections/${connectionId}/conflicts/?status=${q}`,
  );
}

export function resolveConflict(
  connectionId: number | string,
  conflictId: number | string,
  body: { resolution: SyncConflictResolution; field?: string },
) {
  return apiRequest<SyncConflict>(
    `/api/integrations/connections/${connectionId}/conflicts/${conflictId}/resolve/`,
    { method: "POST", body },
  );
}

export function deleteConnection(connectionId: number | string) {
  return apiRequest<null>(`/api/integrations/connections/${connectionId}/`, {
    method: "DELETE",
  });
}
