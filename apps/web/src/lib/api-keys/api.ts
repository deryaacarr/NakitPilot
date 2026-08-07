import { apiRequest } from "@/lib/api/client";

import type { ApiKey, ApiKeyCreated, Paginated, ScopeOption } from "./types";

export function listApiKeyScopes() {
  return apiRequest<{ scopes: ScopeOption[] }>("/api/api-keys/scopes/");
}

export function listApiKeys() {
  return apiRequest<Paginated<ApiKey> | ApiKey[]>("/api/api-keys/");
}

export function createApiKey(body: { name: string; scopes: string[] }) {
  return apiRequest<ApiKeyCreated>("/api/api-keys/", {
    method: "POST",
    body,
  });
}

export function revokeApiKey(id: number | string) {
  return apiRequest<ApiKey>(`/api/api-keys/${id}/revoke/`, {
    method: "POST",
  });
}
