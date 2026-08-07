import { apiRequest } from "@/lib/api/client";

export type AIUsageSummary = {
  organization_id: number;
  user_id: number | null;
  package: string;
  limits: {
    package_monthly_tokens: number;
    daily_user_tokens: number;
    org_budget_monthly: string;
    max_input_chars: number;
    cache_ttl_seconds: number;
  };
  usage: {
    month: {
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
      estimated_cost: string;
    };
    today_user: {
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
      estimated_cost: string;
    } | null;
  };
  controls: string[];
};

export type AIUsageLimits = {
  id: number;
  organization: number;
  package: string;
  package_monthly_tokens: number;
  daily_user_tokens: number;
  org_budget_monthly: string;
  max_input_chars: number;
  cache_ttl_seconds: number;
  is_active: boolean;
};

export function fetchAIUsageSummary() {
  return apiRequest<AIUsageSummary>("/api/ai-usage/summary/");
}

export function fetchAIUsageLimits() {
  return apiRequest<AIUsageLimits>("/api/ai-usage/limits/");
}
