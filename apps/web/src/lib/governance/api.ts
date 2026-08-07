import { apiRequest } from "@/lib/api/client";

export function fetchCustomRoles() {
  return apiRequest<{ results: Array<Record<string, unknown>> }>("/api/organizations/roles/");
}

export function fetchBranches() {
  return apiRequest<{ results: Array<{ id: number; name: string; code: string }> }>(
    "/api/organizations/branches/",
  );
}

export function fetchSessions() {
  return apiRequest<{ results: Array<Record<string, unknown>> }>("/api/auth/sessions/");
}

export function revokeSession(id: number) {
  return apiRequest<{ revoked: boolean }>(`/api/auth/sessions/${id}/revoke/`, { method: "POST", body: {} });
}

export function revokeAllSessions() {
  return apiRequest<{ revoked_count: number }>("/api/auth/sessions/revoke-all/", {
    method: "POST",
    body: {},
  });
}

export function fetchRetention() {
  return apiRequest<Record<string, unknown>>("/api/governance/retention/");
}

export function fetchApprovals() {
  return apiRequest<{ results: Array<Record<string, unknown>> }>("/api/governance/approvals/");
}

export function fetchExports() {
  return apiRequest<{ results: Array<Record<string, unknown>> }>("/api/governance/exports/");
}

export function startExport(datasets: string[]) {
  return apiRequest<Record<string, unknown>>("/api/governance/exports/", {
    method: "POST",
    body: { datasets },
  });
}

export function fetchAccessReport() {
  return apiRequest<{ results: Array<Record<string, unknown>> }>("/api/governance/access-report/");
}

export function fetchInventory() {
  return apiRequest<{ results: Array<Record<string, unknown>> }>("/api/governance/inventory/");
}

export function fetchSsoProviders() {
  return apiRequest<{ results: Array<Record<string, unknown>> }>("/api/governance/sso/providers/");
}

export function requestDeletion(reason: string) {
  return apiRequest<Record<string, unknown>>("/api/governance/deletion-requests/", {
    method: "POST",
    body: { target_type: "organization", reason },
  });
}

export function maskPreview(phone: string, email: string, tax_number: string) {
  return apiRequest<{ phone: string; email: string; tax_number: string }>(
    "/api/governance/mask-preview/",
    { method: "POST", body: { phone, email, tax_number } },
  );
}
