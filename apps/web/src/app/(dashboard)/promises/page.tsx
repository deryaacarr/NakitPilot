import type { Metadata } from "next";
import { Suspense } from "react";

import { PromiseExperience } from "@/components/promises/promise-experience";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";

export const metadata: Metadata = {
  title: "Ödeme sözleri",
};

export default function PaymentPromisesPage() {
  return (
    <Suspense fallback={<LoadingSkeleton className="h-48" />}>
      <PromiseExperience />
    </Suspense>
  );
}
