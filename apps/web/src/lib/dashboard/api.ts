import { apiRequest } from "@/lib/api/client";

import type { DashboardOverview, DashboardRangePreset } from "./types";

export type DashboardQuery = {
  range?: DashboardRangePreset;
  from?: string;
  to?: string;
};

export function fetchDashboardOverview(query: DashboardQuery = {}) {
  return apiRequest<DashboardOverview>("/api/dashboard/", {
    query: {
      range: query.range ?? "week",
      from: query.from,
      to: query.to,
    },
  });
}
