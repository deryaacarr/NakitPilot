import type { Metadata } from "next";

import { PerformanceReportView } from "@/components/reports/performance-report-view";

export const metadata: Metadata = {
  title: "Tahsilat performansı",
};

export default function PerformanceReportPage() {
  return <PerformanceReportView />;
}
