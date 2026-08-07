import type { Metadata } from "next";

import { CustomerForm } from "@/components/customers/customer-form";

export const metadata: Metadata = {
  title: "Yeni müşteri",
};

export default function NewCustomerPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Yeni müşteri</h1>
        <p className="mt-1 text-sm text-slate-600">Cari hesap oluştur</p>
      </div>
      <CustomerForm mode="create" />
    </div>
  );
}
