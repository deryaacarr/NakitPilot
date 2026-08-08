import { apiRequest } from "@/lib/api/client";

import type { CashFlowForecastResponse, ScenarioRunResponse } from "./types";

export function fetchCashFlowForecast(params: { weeks?: number; week_start?: string } = {}) {
  return apiRequest<CashFlowForecastResponse>("/api/forecast/cash-flow", {
    query: {
      weeks: params.weeks ?? 13,
      ...(params.week_start ? { week_start: params.week_start } : {}),
    },
  });
}

export function runForecastScenario(body: {
  scenario_type?: string;
  weeks?: number;
  variables?: {
    average_delay_days_delta?: number;
    collection_probability_factor?: number | string;
    non_paying_customer_ids?: number[];
  };
}) {
  return apiRequest<ScenarioRunResponse>("/api/forecast/scenarios/run/", {
    method: "POST",
    body: {
      scenario_type: body.scenario_type ?? "CUSTOM",
      weeks: body.weeks ?? 13,
      variables: body.variables ?? {},
    },
  });
}
