import type { Metadata } from "next";
import { Suspense } from "react";

import { InvoiceListView } from "@/components/invoices/invoice-list-view";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";

export const metadata: Metadata = {
  title: "Faturalar",
};

export default function InvoicesPage() {
  return (
    <Suspense fallback={<LoadingSkeleton className="h-48" />}>
      <InvoiceListView />
    </Suspense>
  );
}
