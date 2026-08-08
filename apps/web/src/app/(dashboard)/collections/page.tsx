import type { Metadata } from "next";

import { CollectionsBoard } from "@/components/collections/collections-board";

export const metadata: Metadata = {
  title: "Günlük çalışma",
};

export default function CollectionsPage() {
  return <CollectionsBoard />;
}
