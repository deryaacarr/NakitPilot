import type { Metadata } from "next";

import { CollectionCalendar } from "@/components/collections/collection-calendar";

export const metadata: Metadata = {
  title: "Tahsilat takvimi",
};

export default function CollectionCalendarPage() {
  return <CollectionCalendar />;
}
