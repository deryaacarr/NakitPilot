"use client";

import { formatDate, formatMoney } from "@/lib/customers/format";

/** NP-453 — contextual financial helpers under form fields. */
export function PaymentFinancialHint({
  openBalance,
  amount,
  currency = "TRY",
}: {
  openBalance: string | null | undefined;
  amount: string;
  currency?: string;
}) {
  if (openBalance == null) return null;
  const open = Number(openBalance);
  const pay = Number(amount);
  const remaining =
    Number.isFinite(open) && Number.isFinite(pay) ? Math.max(0, open - pay) : null;

  return (
    <div className="rounded-[var(--radius-md)] border border-border-default bg-surface-secondary/50 px-3 py-2 text-xs text-muted">
      <p>
        Açık bakiye:{" "}
        <span className="font-semibold text-foreground">{formatMoney(openBalance, currency)}</span>
      </p>
      {remaining != null && amount.trim() ? (
        <p className="mt-0.5">
          Bu ödeme sonrası kalan:{" "}
          <span className="font-semibold text-foreground">
            {formatMoney(remaining.toFixed(2), currency)}
          </span>
        </p>
      ) : null}
    </div>
  );
}

export function InvoiceFinancialHint({
  paymentTermDays,
  suggestedDue,
}: {
  paymentTermDays: number | null | undefined;
  suggestedDue: string | null | undefined;
}) {
  if (paymentTermDays == null && !suggestedDue) return null;
  return (
    <div className="rounded-[var(--radius-md)] border border-border-default bg-surface-secondary/50 px-3 py-2 text-xs text-muted">
      {paymentTermDays != null ? (
        <p>
          Müşteri varsayılan vadesi:{" "}
          <span className="font-semibold text-foreground">{paymentTermDays} gün</span>
        </p>
      ) : null}
      {suggestedDue ? (
        <p className="mt-0.5">
          Önerilen vade:{" "}
          <span className="font-semibold text-foreground">{formatDate(suggestedDue)}</span>
        </p>
      ) : null}
    </div>
  );
}
