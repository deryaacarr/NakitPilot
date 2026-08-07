import { apiRequest } from "@/lib/api/client";
import type { ApiResult } from "@/lib/errors";

export type WorkflowLifecycleStatus = "draft" | "published" | "archived";

export type WorkflowSummary = {
  id: number;
  name: string;
  description: string;
  trigger_type: string;
  status: WorkflowLifecycleStatus;
  workflow_key: string;
  version: number;
  published_at: string | null;
  is_active: boolean;
  priority: number;
  canvas_meta: Record<string, unknown>;
  step_count: number;
  created_at: string;
  updated_at: string;
};

export type WorkflowGraphStep = {
  id?: number;
  client_key: string;
  name: string;
  step_type: string;
  config: Record<string, unknown>;
  order?: number;
  position_x: number;
  position_y: number;
  is_active?: boolean;
  stop_on_match?: boolean;
};

export type WorkflowGraphEdge = {
  id?: number;
  source: string;
  target: string;
  source_handle: string;
};

export type WorkflowDetail = WorkflowSummary & {
  graph: {
    steps: WorkflowGraphStep[];
    edges: WorkflowGraphEdge[];
    canvas_meta: Record<string, unknown>;
  };
};

export type WorkflowMeta = {
  triggers: Array<{ value: string; label: string }>;
  step_types: Array<{ value: string; label: string }>;
  action_types: Array<{ value: string; label: string }>;
  operators: Array<{ value: string; label: string }>;
  fields: Array<{ value: string; label: string }>;
  edge_handles: string[];
  delay_units: string[];
  lifecycle_statuses?: Array<{ value: string; label: string }>;
};

export type WorkflowSimulation = {
  period_days: number;
  as_of: string;
  workflow_id: number;
  workflow_name: string;
  workflow_version: number;
  trigger_type: string;
  events_evaluated: number;
  tasks_created: number;
  messages_sent: number;
  customers_messaged: number;
  critical_notifications: number;
  notifications: number;
  risk_recalculations: number;
  headline: string;
  by_action_type: Record<string, number>;
};

type Paginated<T> = { results: T[]; count?: number };

export function unwrapList<T>(data: Paginated<T> | T[]): T[] {
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

export function listWorkflows(): Promise<ApiResult<Paginated<WorkflowSummary> | WorkflowSummary[]>> {
  return apiRequest("/api/workflows/");
}

export function getWorkflow(id: number | string): Promise<ApiResult<WorkflowDetail>> {
  return apiRequest(`/api/workflows/${id}/`);
}

export function createWorkflow(body: {
  name: string;
  description?: string;
  trigger_type: string;
}): Promise<ApiResult<WorkflowDetail>> {
  return apiRequest("/api/workflows/", { method: "POST", body });
}

export function updateWorkflow(
  id: number | string,
  body: Partial<Pick<WorkflowSummary, "name" | "description" | "trigger_type" | "priority">>,
): Promise<ApiResult<WorkflowDetail>> {
  return apiRequest(`/api/workflows/${id}/`, { method: "PATCH", body });
}

export function deleteWorkflow(id: number | string): Promise<ApiResult<void>> {
  return apiRequest(`/api/workflows/${id}/`, { method: "DELETE" });
}

export function saveWorkflowGraph(
  id: number | string,
  body: {
    steps: WorkflowGraphStep[];
    edges: WorkflowGraphEdge[];
    canvas_meta?: Record<string, unknown>;
  },
): Promise<ApiResult<WorkflowDetail>> {
  return apiRequest(`/api/workflows/${id}/graph/`, { method: "PUT", body });
}

export function publishWorkflow(
  id: number | string,
): Promise<ApiResult<{ published: WorkflowDetail; draft: WorkflowDetail }>> {
  return apiRequest(`/api/workflows/${id}/publish/`, { method: "POST" });
}

export function archiveWorkflow(id: number | string): Promise<ApiResult<WorkflowSummary>> {
  return apiRequest(`/api/workflows/${id}/archive/`, { method: "POST" });
}

/** @deprecated use publishWorkflow */
export function activateWorkflow(id: number | string) {
  return publishWorkflow(id);
}

/** @deprecated use archiveWorkflow */
export function deactivateWorkflow(id: number | string) {
  return archiveWorkflow(id);
}

export function listWorkflowVersions(id: number | string): Promise<ApiResult<WorkflowSummary[]>> {
  return apiRequest(`/api/workflows/${id}/versions/`);
}

export function simulateWorkflow(
  id: number | string,
  body: { days?: number } = { days: 30 },
): Promise<ApiResult<WorkflowSimulation>> {
  return apiRequest(`/api/workflows/${id}/simulate/`, { method: "POST", body });
}

export function getWorkflowMeta(): Promise<ApiResult<WorkflowMeta>> {
  return apiRequest("/api/workflows/meta/");
}

export function testRunWorkflow(
  id: number | string,
  body: { customer_id: number; context?: Record<string, unknown> },
): Promise<ApiResult<{ id: number; status: string }>> {
  return apiRequest(`/api/workflows/${id}/test-run/`, {
    method: "POST",
    body,
  });
}

export function statusLabel(status: string) {
  if (status === "published") return "Yayında";
  if (status === "archived") return "Arşiv";
  return "Taslak";
}
