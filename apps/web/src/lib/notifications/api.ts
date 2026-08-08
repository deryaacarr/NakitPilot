import { apiRequest } from "@/lib/api/client";

export type NotificationAction = {
  label: string;
  href: string;
};

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
  customer_id?: number | null;
  customer_name?: string | null;
  importance_group?: "critical" | "action" | "info" | "system" | string;
  actions?: NotificationAction[];
};

export type AlertsResponse = {
  count: number;
  unread_count: number;
  group_by_customer?: boolean;
  results: DashboardAlert[];
};

export type NotificationPreferences = {
  muted_types: string[];
  mute_info: boolean;
  mute_system: boolean;
  group_by_customer: boolean;
  updated_at?: string;
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
  return apiRequest<{ updated: number; critical_preserved?: boolean }>(
    "/api/notifications/alerts/read-all/",
    { method: "POST" },
  );
}

export function fetchNotificationPreferences() {
  return apiRequest<NotificationPreferences>("/api/notifications/preferences/");
}

export function updateNotificationPreferences(body: Partial<NotificationPreferences>) {
  return apiRequest<NotificationPreferences>("/api/notifications/preferences/", {
    method: "PATCH",
    body,
  });
}

export function normalizeAlertsPayload(
  raw: AlertsResponse | DashboardAlert[] | undefined,
): { alerts: DashboardAlert[]; unreadCount: number; groupByCustomer: boolean } {
  if (!raw) return { alerts: [], unreadCount: 0, groupByCustomer: true };
  if (Array.isArray(raw)) {
    return {
      alerts: raw,
      unreadCount: raw.filter((a) => !a.is_read).length,
      groupByCustomer: true,
    };
  }
  return {
    alerts: raw.results ?? [],
    unreadCount: raw.unread_count ?? (raw.results ?? []).filter((a) => !a.is_read).length,
    groupByCustomer: raw.group_by_customer !== false,
  };
}

export const IMPORTANCE_GROUPS: {
  id: "critical" | "action" | "info" | "system";
  label: string;
}[] = [
  { id: "critical", label: "Kritik" },
  { id: "action", label: "Aksiyon gerekli" },
  { id: "info", label: "Bilgilendirme" },
  { id: "system", label: "Sistem" },
];

export function alertImportance(alert: DashboardAlert): "critical" | "action" | "info" | "system" {
  if (
    alert.importance_group === "critical" ||
    alert.importance_group === "action" ||
    alert.importance_group === "info" ||
    alert.importance_group === "system"
  ) {
    return alert.importance_group;
  }
  if (alert.severity === "CRITICAL" || alert.notification_type === "PROMISE_BROKEN") {
    return "critical";
  }
  if (["IMPORT_COMPLETED", "IMPORT_FAILED", "CASH_GAP"].includes(alert.notification_type)) {
    return "system";
  }
  if (
    ["TASK_DUE", "TASK_OVERDUE", "TASK_ASSIGNED", "PROMISE_DUE", "HIGH_RISK_CUSTOMER"].includes(
      alert.notification_type,
    )
  ) {
    return "action";
  }
  return "info";
}
