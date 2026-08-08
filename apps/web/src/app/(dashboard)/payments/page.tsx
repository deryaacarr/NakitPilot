import type { Metadata } from "next";
import Link from "next/link";

import { PaymentsList } from "@/components/payments/payments-list";

export const metadata: Metadata = {
  title: "Ödemeler",
};

export default function PaymentsPage() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl tracking-tight text-foreground">Ödemeler</h1>
          <p className="mt-1 text-sm text-muted">Kaydedilen tahsilatlar</p>
        </div>
        <Link
          href="/payments/new"
          className="inline-flex h-8 items-center rounded-[var(--radius-md)] bg-primary px-3 text-xs font-semibold text-primary-foreground"
        >
          + Yeni ödeme
        </Link>
      </div>
      <PaymentsList />
    </div>
  );
}
