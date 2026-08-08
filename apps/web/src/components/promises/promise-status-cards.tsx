"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate, formatMoney } from "@/lib/customers/format";
import {
  PROMISE_BOARD_GROUPS,
  PROMISE_STATUS_LABELS,
  type PaymentPromise,
  type PromiseStatusBoard,
} from "@/lib/promises/types";

export function PromiseStatusCards({ board }: { board: PromiseStatusBoard }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {PROMISE_BOARD_GROUPS.map((group) => (
        <section
          key={group.key}
          className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary"
        >
          <header className="flex items-center justify-between border-b border-border-default px-4 py-3">
            <h2 className="text-sm font-semibold text-foreground">{group.title}</h2>
            <Badge tone={group.tone}>{board[group.key].length}</Badge>
          </header>
          <div className="max-h-[22rem] space-y-2 overflow-y-auto p-3">
            {board[group.key].length === 0 ? (
              <EmptyState title="Kayıt yok" description="Bu durumda söz yok." />
            ) : (
              board[group.key].map((promise) => (
                <PromiseStatusCard key={promise.id} promise={promise} />
              ))
            )}
          </div>
        </section>
      ))}
    </div>
  );
}

export function PromiseStatusCard({ promise }: { promise: PaymentPromise }) {
  const paid = promise.paid_amount ?? "0";
  const remaining = promise.remaining_amount ?? promise.amount;
  const delay = promise.delay_days ?? 0;

  return (
    <article className="rounded-[var(--radius-md)] border border-border-default bg-surface-secondary/50 px-3 py-2.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Link
            href={`/customers/${promise.customer}`}
            className="font-semibold text-foreground hover:underline"
          >
            {promise.customer_name}
          </Link>
          <p className="text-xs text-muted">
            {formatDate(promise.promised_date)}
            {promise.invoice_number ? ` · ${promise.invoice_number}` : ""}
          </p>
        </div>
        <Badge
          tone={
            promise.status === "BROKEN"
              ? "danger"
              : promise.status === "FULFILLED"
                ? "success"
                : promise.status === "PARTIALLY_FULFILLED"
                  ? "analysis"
                  : "neutral"
          }
        >
          {PROMISE_STATUS_LABELS[promise.status] ?? promise.status}
        </Badge>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        <Metric label="Söz tutarı" value={formatMoney(promise.amount, promise.currency)} />
        <Metric label="Gerçekleşen" value={formatMoney(paid, promise.currency)} />
        <Metric label="Kalan" value={formatMoney(remaining, promise.currency)} />
        <Metric label="Söz tarihi" value={formatDate(promise.promised_date)} />
        <Metric label="Gecikme" value={delay > 0 ? `${delay} gün` : "—"} />
        <Metric
          label="Sorumlu"
          value={promise.assigned_to_name || promise.assigned_to_email || "—"}
        />
      </dl>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-subtle">{label}</dt>
      <dd className="font-medium text-foreground">{value}</dd>
    </div>
  );
}
