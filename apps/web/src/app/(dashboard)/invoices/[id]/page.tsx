"use client";

import { useParams } from "next/navigation";

import { InvoiceDetailView } from "@/components/invoices/invoice-detail-view";
import { ErrorState } from "@/components/errors";

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  if (!Number.isFinite(id)) {
    return <ErrorState error="Geçersiz fatura" />;
  }

  return <InvoiceDetailView invoiceId={id} />;
}
