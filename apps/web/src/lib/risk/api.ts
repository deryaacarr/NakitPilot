import { apiRequest } from "@/lib/api/client";

export type RiskMonitoringPayload = {
  lookback_days: number;
  n_labeled: number;
  target_label: string;
  technical_visible: boolean;
  business: {
    predicted_vs_actual_collection: {
      n: number;
      predicted_collection: number;
      predicted_no_collection: number;
      actual_collection: number;
      actual_no_collection: number;
      predicted_and_actual_collection: number;
      collection_hit_rate: number | null;
    };
    delay_rate_by_risk_level: Array<{
      risk_level: string;
      n: number;
      with_delay: number;
      delay_rate: number | null;
    }>;
  };
  technical: {
    precision: number | null;
    recall: number | null;
    roc_auc: number | null;
    calibration_error: number | null;
    n: number;
  } | null;
};

export type CustomerSummaryPayload = {
  customer_id: number;
  organization_id: number;
  as_of: string;
  summary: string;
  paragraphs: string[];
  facts: Array<{ key: string; value: string | number; display: string }>;
  sources: Array<{
    type: string;
    id: number | null;
    label: string;
    field: string;
    value: string | number | null;
    url_hint?: string | null;
  }>;
};

export function fetchRiskMonitoring(lookbackDays = 180) {
  return apiRequest<RiskMonitoringPayload>("/api/risk/monitoring/", {
    query: { lookback_days: lookbackDays },
  });
}

export function fetchCustomerSummary(customerId: number | string) {
  return apiRequest<CustomerSummaryPayload>(`/api/customers/${customerId}/summary/`);
}
