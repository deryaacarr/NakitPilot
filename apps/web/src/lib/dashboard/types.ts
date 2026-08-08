export type DashboardRangePreset = "today" | "week" | "month" | "last_30" | "custom";

export type DashboardRole =
  | "OWNER"
  | "ADMIN"
  | "FINANCE_MANAGER"
  | "COLLECTION_AGENT"
  | "VIEWER"
  | "EXTERNAL_LAWYER"
  | string;

export type KpiComparison = {
  previous: string | null;
  change_pct: number | null;
  direction_good_when: "up" | "down";
  label: string;
};

export type DashboardCards = {
  open_receivables: string;
  overdue_receivables: string;
  expected_this_week: string;
  promises_today: number;
  promises_broken: number;
  critical_customers: number;
  overdue_tasks: number;
  today_tasks?: number;
};

export type DashboardMeta = {
  customer_count: number;
  open_invoice_count: number;
  overdue_invoice_count: number;
  is_empty: boolean;
};

export type DashboardSummary = {
  as_of: string;
  currency: string;
  week_start: string;
  date_from?: string;
  date_to?: string;
  cards: DashboardCards;
  comparisons?: Record<string, KpiComparison>;
  meta?: DashboardMeta;
};

export type AgingGroup = {
  code: string;
  label: string;
  customer_count: number;
  invoice_count: number;
  open_amount: string;
  share: string;
  share_percent: number;
};

export type AgingReport = {
  as_of: string;
  currency: string;
  total_open_amount: string;
  groups: AgingGroup[];
};

export type CallListRow = {
  customer_id: number;
  customer_name: string;
  customer_code: string;
  customer_phone?: string;
  overdue_balance: string;
  oldest_overdue_days: number | null;
  risk_status: string;
  risk_score: number;
  last_contact_at: string | null;
  payment_promise: {
    id: number;
    amount: string;
    promised_date: string;
    status: string;
  } | null;
  open_task_id?: number | null;
  priority_score: number;
  priority: string;
  priority_reason?: string;
  suggested_action?: string;
};

export type CallList = {
  as_of: string;
  results: CallListRow[];
};

export type PerformanceWeek = {
  week_start: string;
  week_end: string;
  actual: string;
  expected: string;
};

export type PerformanceReport = {
  date_from: string;
  date_to: string;
  currency: string;
  weekly: PerformanceWeek[];
  totals: { actual: string; expected: string };
  tasks_by_user: { user_id: number | null; user_name: string; completed_count: number }[];
  promises: { kept: number; broken: number };
};

export type AgentTaskRow = {
  id: number;
  title: string;
  status: string;
  due_date: string | null;
  customer_id: number;
  customer_name: string;
  priority: string;
  priority_score: number;
};

export type AgentWorkboard = {
  as_of: string;
  today_tasks: AgentTaskRow[];
  overdue_tasks: AgentTaskRow[];
  promises_today: Array<{
    id: number;
    customer_id: number;
    customer_name: string;
    amount: string;
    promised_date: string;
    status: string;
  }>;
  recent_activities: Array<{
    id: number;
    customer_id: number;
    customer_name: string;
    activity_type: string;
    summary: string;
    occurred_at: string;
  }>;
};

export type RiskDistribution = {
  groups: Array<{ status: string; count: number }>;
};

export type ForecastSnippet = {
  currency: string;
  weeks: Array<{ week_start: string; expected_amount: string }>;
  total_expected: string;
};

export type DashboardOverview = {
  range: { preset: DashboardRangePreset; date_from: string; date_to: string };
  summary: DashboardSummary;
  aging: AgingReport;
  call_list: CallList;
  performance: PerformanceReport;
  agent?: AgentWorkboard;
  risk_distribution?: RiskDistribution;
  forecast?: ForecastSnippet;
  role?: DashboardRole | null;
};
