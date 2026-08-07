import { apiRequest } from "@/lib/api/client";

export type DashboardAlert = {
  id: number;
  title: string;
  body: string;
  severity: string;
  notification_type: string;
  category: string;
  entity_type: string;
  entity_id: string;
  href: string;
  is_read: boolean;
  created_at: string;
};

export type AlertsResponse = {
  count: number;
  unread_count: number;
  results: DashboardAlert[];
};

export function fetchDashboardAlerts(query?: {
  unread?: boolean;
  limit?: number;
  offset?: number;
}) {
  return apiRequest<AlertsResponse | DashboardAlert[]>("/api/notifications/alerts/", {
    query: {
      unread: query?.unread ? "true" : undefined,
      limit: query?.limit,
      offset: query?.offset,
    },
  });
}

export function markAlertRead(id: number) {
  return apiRequest<DashboardAlert>(`/api/notifications/alerts/${id}/read/`, {
    method: "POST",
  });
}

export function markAllAlertsRead() {
  return apiRequest<{ updated: number }>("/api/notifications/alerts/read-all/", {
    method: "POST",
  });
}

export function normalizeAlertsPayload(
  raw: AlertsResponse | DashboardAlert[] | undefined,
): { alerts: DashboardAlert[]; unreadCount: number } {
  if (!raw) return { alerts: [], unreadCount: 0 };
  if (Array.isArray(raw)) {
    return {
      alerts: raw,
      unreadCount: raw.filter((a) => !a.is_read).length,
    };
  }
  return {
    alerts: raw.results ?? [],
    unreadCount: raw.unread_count ?? (raw.results ?? []).filter((a) => !a.is_read).length,
  };
}
