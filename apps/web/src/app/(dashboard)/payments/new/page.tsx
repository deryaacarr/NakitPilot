import type { Metadata } from "next";

import { PaymentCreateForm } from "@/components/payments/payment-create-form";

export const metadata: Metadata = {
  title: "Yeni ödeme",
};

export default function NewPaymentPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-foreground">Yeni ödeme</h1>
        <p className="mt-1 text-sm text-muted">Tahsilatı kaydet ve faturalara dağıt</p>
      </div>
      <PaymentCreateForm />
    </div>
  );
}
