import { apiRequest } from "@/lib/api/client";

export type SavedTableView = {
  id: number;
  organization: number;
  resource: string;
  name: string;
  filters: Record<string, string>;
  hidden_columns: string[];
  sort: { id?: string; direction?: "asc" | "desc" };
  is_default: boolean;
  is_shared: boolean;
  share_token: string;
  created_by: number | null;
  created_at: string;
  updated_at: string;
};

export type SavedViewInput = {
  resource: string;
  name: string;
  filters?: Record<string, string>;
  hidden_columns?: string[];
  sort?: { id?: string; direction?: "asc" | "desc" };
  is_default?: boolean;
  is_shared?: boolean;
};

export function listSavedViews(resource: string) {
  return apiRequest<SavedTableView[] | { results: SavedTableView[] }>("/api/saved-views/", {
    query: { resource },
  });
}

export function createSavedView(body: SavedViewInput) {
  return apiRequest<SavedTableView>("/api/saved-views/", { method: "POST", body });
}

export function updateSavedView(id: number, body: Partial<SavedViewInput>) {
  return apiRequest<SavedTableView>(`/api/saved-views/${id}/`, { method: "PATCH", body });
}

export function deleteSavedView(id: number) {
  return apiRequest<null>(`/api/saved-views/${id}/`, { method: "DELETE" });
}

export function setDefaultSavedView(id: number) {
  return apiRequest<SavedTableView>(`/api/saved-views/${id}/set-default/`, { method: "POST", body: {} });
}

export function fetchSavedViewByToken(token: string) {
  return apiRequest<SavedTableView>(`/api/saved-views/by-token/${token}/`);
}

export function normalizeSavedViews(
  data: SavedTableView[] | { results: SavedTableView[] },
): SavedTableView[] {
  if (Array.isArray(data)) return data;
  return data.results || [];
}
