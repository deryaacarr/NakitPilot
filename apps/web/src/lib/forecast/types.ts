export type ForecastWeek = {
  week_start: string;
  nominal: string;
  expected: string;
  optimistic: string;
  pessimistic: string;
  actual?: string | null;
};

export type ForecastTopInvoice = {
  id: number;
  number: string;
  customer_id: number;
  customer_name: string;
  open_amount: string;
  expected_amount: string;
  due_date: string;
  probability: string;
};

export type ForecastInsight = {
  what: string;
  why: string;
  action: string;
};

export type ForecastWeekDetail = {
  week_start: string;
  week_end: string;
  summary: string;
  expected: string;
  open_total: string;
  risk_reduction: string;
  high_risk_amount?: string;
  vs_previous_week_pct?: number | null;
  highest_risk_customer: {
    id: number;
    name: string;
    risk_score: number;
    risk_status: string;
  } | null;
  insight?: ForecastInsight;
  top_invoices: ForecastTopInvoice[];
};

export type CashFlowForecastResponse = {
  weeks: ForecastWeek[];
  currency: string;
  as_of: string;
  detail?: ForecastWeekDetail;
};

export type ScenarioRunResponse = {
  scenario_type: string;
  variables?: Record<string, unknown>;
  currency?: string;
  timeline?: Array<{
    week_start: string;
    expected_collection: string;
    expected_outflow?: string;
    ending_balance?: string;
  }>;
  summary?: {
    min_cash?: string;
    total_expected_collection?: string;
  };
};
