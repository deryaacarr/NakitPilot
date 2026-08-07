import type { Metadata } from "next";

import { InvoiceListView } from "@/components/invoices/invoice-list-view";

export const metadata: Metadata = {
  title: "Faturalar",
};

export default function InvoicesPage() {
  return <InvoiceListView />;
}
