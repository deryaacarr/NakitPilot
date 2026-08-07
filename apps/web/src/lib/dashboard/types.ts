export type DashboardRangePreset = "today" | "week" | "month" | "last_30" | "custom";

export type DashboardCards = {
  open_receivables: string;
  overdue_receivables: string;
  expected_this_week: string;
  promises_today: number;
  promises_broken: number;
  critical_customers: number;
  overdue_tasks: number;
};

export type DashboardSummary = {
  as_of: string;
  currency: string;
  week_start: string;
  date_from?: string;
  date_to?: string;
  cards: DashboardCards;
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
  priority_score: number;
  priority: string;
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

export type DashboardOverview = {
  range: { preset: DashboardRangePreset; date_from: string; date_to: string };
  summary: DashboardSummary;
  aging: AgingReport;
  call_list: CallList;
  performance: PerformanceReport;
};
