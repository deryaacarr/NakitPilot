"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { CustomerContactsPanel } from "@/components/customers/customer-contacts-panel";
import { CustomerForm } from "@/components/customers/customer-form";
import { ErrorState } from "@/components/errors";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { getCustomer } from "@/lib/customers/api";
import type { Customer } from "@/lib/customers/types";
import type { AppError } from "@/lib/errors";

export default function EditCustomerPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [error, setError] = useState<AppError | string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!Number.isFinite(id)) {
      return;
    }
    let cancelled = false;
    void Promise.resolve().then(async () => {
      const result = await getCustomer(id);
      if (cancelled) return;
      setLoading(false);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setCustomer(result.data);
    });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!Number.isFinite(id)) {
    return <ErrorState error="Geçersiz müşteri" />;
  }
  if (loading) return <LoadingSkeleton lines={8} />;
  if (error) return <ErrorState error={error} />;
  if (!customer) return null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Müşteri düzenle</h1>
        <p className="mt-1 text-sm text-slate-600">{customer.name}</p>
      </div>
      <CustomerForm
        mode="edit"
        customer={customer}
        contactsSlot={<CustomerContactsPanel customerId={customer.id} />}
      />
    </div>
  );
}
