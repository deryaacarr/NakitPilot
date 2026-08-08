import type { Metadata } from "next";
import { Suspense } from "react";

import { AllTasksBoard } from "@/components/collections/all-tasks-board";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";

export const metadata: Metadata = {
  title: "Tüm görevler",
};

export default function AllCollectionTasksPage() {
  return (
    <Suspense fallback={<LoadingSkeleton className="h-48" />}>
      <AllTasksBoard />
    </Suspense>
  );
}
