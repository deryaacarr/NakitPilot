import type { Metadata } from "next";

import { DashboardHomeView } from "@/components/dashboard/dashboard-home-view";

export const metadata: Metadata = {
  title: "Özet",
};

export default function DashboardHomePage() {
  return <DashboardHomeView />;
}
