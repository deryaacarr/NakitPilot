import type { Metadata } from "next";

import { RiskMonitoringView } from "@/components/risk/risk-monitoring-view";

export const metadata: Metadata = {
  title: "Model doğruluk",
};

export default function RiskMonitoringPage() {
  return <RiskMonitoringView />;
}
