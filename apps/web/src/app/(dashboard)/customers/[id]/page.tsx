"use client";

import { useParams } from "next/navigation";

import { CustomerDetailView } from "@/components/customers/customer-detail-view";
import { ErrorState } from "@/components/errors";

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  if (!Number.isFinite(id)) {
    return <ErrorState error="Geçersiz müşteri" />;
  }

  return <CustomerDetailView customerId={id} />;
}
