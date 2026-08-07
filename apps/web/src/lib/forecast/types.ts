export type ForecastWeek = {
  week_start: string;
  nominal: string;
  expected: string;
  optimistic: string;
  pessimistic: string;
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

export type ForecastWeekDetail = {
  week_start: string;
  week_end: string;
  summary: string;
  expected: string;
  open_total: string;
  risk_reduction: string;
  highest_risk_customer: {
    id: number;
    name: string;
    risk_score: number;
    risk_status: string;
  } | null;
  top_invoices: ForecastTopInvoice[];
};

export type CashFlowForecastResponse = {
  weeks: ForecastWeek[];
  currency: string;
  as_of: string;
  detail?: ForecastWeekDetail;
};
