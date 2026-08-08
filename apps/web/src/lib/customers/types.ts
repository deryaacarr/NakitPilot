export type RiskStatus = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type CustomerContact = {
  id: number;
  customer: number;
  organization: number;
  full_name: string;
  title: string;
  email: string;
  phone: string;
  is_primary: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type Customer = {
  id: number;
  organization: number;
  code: string;
  name: string;
  tax_number: string;
  email: string;
  phone: string;
  city: string;
  sector: string;
  payment_term_days: number;
  credit_limit: string;
  risk_status: RiskStatus;
  risk_score: number;
  assigned_user: number | null;
  assigned_user_name: string | null;
  collection_strategy?: string;
  notes: string;
  last_contact_at: string | null;
  is_active: boolean;
  open_balance: string;
  overdue_balance: string;
  disputed_balance?: string;
  avg_delay_days: number | null;
  oldest_overdue_days: number | null;
  last_payment_date?: string | null;
  last_payment_amount?: string | null;
  last_payment_currency?: string | null;
  primary_contact_name: string | null;
  created_at: string;
  updated_at: string;
  contacts?: CustomerContact[];
};

export type FinancialSummarySeries = {
  month: string;
  amount?: string;
  days?: number | null;
  rate?: number | null;
  paid_count?: number;
};

export type CustomerFinancialSummary = {
  as_of: string;
  currency: string;
  monthly_invoices: FinancialSummarySeries[];
  monthly_payments: FinancialSummarySeries[];
  open_balance_trend: FinancialSummarySeries[];
  avg_delay_trend: FinancialSummarySeries[];
  on_time_payment_rate: FinancialSummarySeries[];
  insights: string[];
};

export type CustomerInput = {
  code?: string;
  name: string;
  tax_number?: string;
  email?: string;
  phone?: string;
  city?: string;
  sector?: string;
  payment_term_days?: number;
  credit_limit?: string;
  risk_status?: RiskStatus;
  risk_score?: number;
  assigned_user?: number | null;
  collection_strategy?: string;
  notes?: string;
  is_active?: boolean;
};

export type CustomerContactInput = {
  full_name: string;
  title?: string;
  email?: string;
  phone?: string;
  is_primary?: boolean;
  notes?: string;
};

export type CustomerListParams = {
  search?: string;
  risk_status?: string;
  assigned_user?: string;
  city?: string;
  sector?: string;
  is_active?: string;
  has_overdue?: string;
  ordering?: string;
  page?: number;
  page_size?: number;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type RiskHistoryPoint = {
  score: number;
  level: RiskStatus;
  at: string;
  reasons: { code: string; label: string; points: number }[];
};

export type RiskExplanationReason = {
  sign: "+" | "-";
  text: string;
  code: string;
  points: number;
};

export type RiskExplanation = {
  customer_id: number;
  score: number;
  level: RiskStatus;
  level_label: string;
  headline: string;
  reasons: RiskExplanationReason[];
  as_of: string;
  snapshot_id?: number;
  calculated_at?: string;
};

export const RISK_LABELS: Record<RiskStatus, string> = {
  LOW: "Düşük",
  MEDIUM: "Orta",
  HIGH: "Yüksek",
  CRITICAL: "Kritik",
};
