import type { DashboardRole } from "./types";

export type WidgetId =
  | "call_priority"
  | "agent_today_tasks"
  | "agent_overdue_tasks"
  | "agent_promises"
  | "agent_activities"
  | "kpi_financial"
  | "kpi_agent"
  | "performance"
  | "team_performance"
  | "aging"
  | "risk_distribution"
  | "forecast";

export type WidgetDef = {
  id: WidgetId;
  label: string;
  layer: 1 | 2 | 3;
  roles: Array<"manager" | "agent">;
};

export const WIDGET_CATALOG: WidgetDef[] = [
  { id: "call_priority", label: "Bugün kimi aramalıyım?", layer: 1, roles: ["manager", "agent"] },
  { id: "agent_today_tasks", label: "Bugünkü görevler", layer: 1, roles: ["agent"] },
  { id: "agent_overdue_tasks", label: "Gecikmiş görevler", layer: 1, roles: ["agent"] },
  { id: "agent_promises", label: "Bugünkü ödeme sözleri", layer: 1, roles: ["agent"] },
  { id: "agent_activities", label: "Son aktiviteler", layer: 1, roles: ["agent"] },
  { id: "kpi_financial", label: "Finansal KPI’lar", layer: 2, roles: ["manager"] },
  { id: "kpi_agent", label: "Görev KPI’ları", layer: 2, roles: ["agent"] },
  { id: "performance", label: "Tahsilat performansı", layer: 3, roles: ["manager"] },
  { id: "team_performance", label: "Ekip performansı", layer: 3, roles: ["manager"] },
  { id: "aging", label: "Yaşlandırma", layer: 3, roles: ["manager"] },
  { id: "risk_distribution", label: "Risk dağılımı", layer: 3, roles: ["manager"] },
  { id: "forecast", label: "Forecast", layer: 3, roles: ["manager"] },
];

const PREFS_KEY = "nakitpilot.dashboard_widgets";

export function dashboardPersona(role?: DashboardRole | null): "manager" | "agent" {
  if (role === "COLLECTION_AGENT") return "agent";
  return "manager";
}

export function defaultVisibleWidgets(persona: "manager" | "agent"): WidgetId[] {
  return WIDGET_CATALOG.filter((w) => w.roles.includes(persona)).map((w) => w.id);
}

export function loadWidgetPrefs(persona: "manager" | "agent"): WidgetId[] {
  try {
    const raw = window.localStorage.getItem(`${PREFS_KEY}.${persona}`);
    if (!raw) return defaultVisibleWidgets(persona);
    const parsed = JSON.parse(raw) as WidgetId[];
    const allowed = new Set(defaultVisibleWidgets(persona));
    const filtered = parsed.filter((id) => allowed.has(id));
    return filtered.length ? filtered : defaultVisibleWidgets(persona);
  } catch {
    return defaultVisibleWidgets(persona);
  }
}

export function saveWidgetPrefs(persona: "manager" | "agent", ids: WidgetId[]) {
  window.localStorage.setItem(`${PREFS_KEY}.${persona}`, JSON.stringify(ids));
}

export function isWidgetVisible(visible: WidgetId[], id: WidgetId) {
  return visible.includes(id);
}
