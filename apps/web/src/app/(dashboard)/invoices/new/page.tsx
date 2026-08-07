import type { Metadata } from "next";

import { InvoiceCreateForm } from "@/components/invoices/invoice-create-form";

export const metadata: Metadata = {
  title: "Yeni fatura",
};

export default function NewInvoicePage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Yeni fatura</h1>
        <p className="mt-1 text-sm text-slate-600">Cari alacak faturası oluştur</p>
      </div>
      <InvoiceCreateForm />
    </div>
  );
}
