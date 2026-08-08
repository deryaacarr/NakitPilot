import type { Metadata } from "next";
import { Suspense } from "react";

import { PromiseCalendarBoard } from "@/components/promises/promise-calendar-board";
import { PromiseQuickCreate } from "@/components/promises/promise-quick-create";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";

export const metadata: Metadata = {
  title: "Ödeme sözleri",
};

export default function PaymentPromisesPage() {
  return (
    <div className="space-y-4">
      <Suspense fallback={null}>
        <PromiseQuickCreate />
      </Suspense>
      <Suspense fallback={<LoadingSkeleton className="h-48" />}>
        <PromiseCalendarBoard />
      </Suspense>
    </div>
  );
}
