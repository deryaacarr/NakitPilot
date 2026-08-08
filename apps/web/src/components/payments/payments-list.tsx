"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { EmptyState } from "@/components/ui/empty-state";
import { Money } from "@/components/ui/money";
import { TableSkeleton } from "@/components/ui/loading-skeleton";
import { listPayments, type Payment } from "@/lib/payments/api";
import { EMPTY_PRESETS } from "@/lib/ui/empty-presets";

export function PaymentsList() {
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

  if (loading) return <TableSkeleton rows={6} />;
  if (error) {
    return (
      <ErrorState
        error={error}
        onRetry={() => {
          setLoading(true);
          setError(null);
          void listPayments({ page_size: 50 }).then((res) => {
            setLoading(false);
            if (!res.ok) {
              setError(res.error.message);
              return;
            }
            setRows(res.data.results || []);
          });
        }}
      />
    );
  }
  if (!rows.length) {
    return (
      <EmptyState
        title={EMPTY_PRESETS.payments.title}
        description={EMPTY_PRESETS.payments.description}
        why={EMPTY_PRESETS.payments.why}
        actionLabel={EMPTY_PRESETS.payments.actionLabel}
        actionHref={EMPTY_PRESETS.payments.actionHref}
      />
    );
  }

  return (
    <>
      {/* NP-482 mobile cards */}
      <ul className="space-y-2 md:hidden" role="list">
        {rows.map((p) => (
          <li
            key={p.id}
            className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-3"
          >
            <div className="flex items-start justify-between gap-2">
              <Link
                href={`/customers/${p.customer}`}
                className="font-semibold text-primary hover:underline"
              >
                {p.customer_name}
              </Link>
              <Money value={p.amount} currency={p.currency} size="table" />
            </div>
            <p className="mt-1 text-sm text-muted">
              {p.payment_date}
              {p.reference ? ` · ${p.reference}` : ""}
            </p>
          </li>
        ))}
      </ul>

      <div className="hidden overflow-x-auto rounded-[var(--radius-lg)] border border-border-default md:block">
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
                  <Link
                    href={`/customers/${p.customer}`}
                    className="font-medium text-primary hover:underline"
                  >
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
    </>
  );
}
