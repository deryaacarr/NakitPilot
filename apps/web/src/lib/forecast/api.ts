import { apiRequest } from "@/lib/api/client";

import type { CashFlowForecastResponse } from "./types";

export function fetchCashFlowForecast(params: { weeks?: number; week_start?: string } = {}) {
  return apiRequest<CashFlowForecastResponse>("/api/forecast/cash-flow", {
    query: {
      weeks: params.weeks ?? 13,
      ...(params.week_start ? { week_start: params.week_start } : {}),
    },
  });
}
