import type { Metadata } from "next";

import { NotificationsView } from "@/components/notifications/notifications-view";

export const metadata: Metadata = {
  title: "Bildirimler",
};

export default function NotificationsPage() {
  return <NotificationsView />;
}
