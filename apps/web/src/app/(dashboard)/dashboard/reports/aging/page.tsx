import type { Metadata } from "next";

import { AgingReportView } from "@/components/reports/aging-report-view";

export const metadata: Metadata = {
  title: "Yaşlandırma",
};

export default function AgingReportPage() {
  return <AgingReportView />;
}
