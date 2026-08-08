"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { Money } from "@/components/ui/money";
import { listPayments, type Payment } from "@/lib/payments/api";

export function PaymentsList() {
  const router = useRouter();
  const [rows, setRows] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const res = await listPayments({ page_size: 50 });
      if (cancelled) return;
      setLoading(false);
      if (!res.ok) {
        setError(res.error.message);
        return;
      }
      setRows(res.data.results || []);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <LoadingSkeleton className="h-48" />;
  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!rows.length) {
    return (
      <EmptyState
        title="Henüz ödeme yok"
        description="İlk ödemeyi kaydederek tahsilatı takip edin."
        actionLabel="Yeni ödeme"
        onAction={() => router.push("/payments/new")}
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border-default">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-surface-secondary text-xs uppercase tracking-wide text-subtle">
          <tr>
            <th className="px-4 py-3 font-semibold">Tarih</th>
            <th className="px-4 py-3 font-semibold">Müşteri</th>
            <th className="px-4 py-3 font-semibold">Tutar</th>
            <th className="px-4 py-3 font-semibold">Referans</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id} className="border-t border-border-default">
              <td className="px-4 py-3 text-muted">{p.payment_date}</td>
              <td className="px-4 py-3">
                <Link href={`/customers/${p.customer}`} className="font-medium text-primary hover:underline">
                  {p.customer_name}
                </Link>
              </td>
              <td className="px-4 py-3">
                <Money value={p.amount} currency={p.currency} size="table" />
              </td>
              <td className="px-4 py-3 text-muted">{p.reference || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
