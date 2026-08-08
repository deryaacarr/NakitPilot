"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { Drawer } from "@/components/ui/drawer";
import { Money } from "@/components/ui/money";
import { StatusChip } from "@/components/ui/status-chip";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { getCustomer } from "@/lib/customers/api";
import type { Customer } from "@/lib/customers/types";
import { RISK_LABELS, type RiskStatus } from "@/lib/customers/types";
import { listInvoices } from "@/lib/invoices/api";
import type { Invoice } from "@/lib/invoices/types";
import { listPaymentPromises } from "@/lib/promises/api";
import type { PaymentPromise } from "@/lib/promises/types";
import { fetchCustomerSummary } from "@/lib/risk/api";

function riskTone(status: string) {
  if (status === "LOW") return "success" as const;
  if (status === "MEDIUM") return "warning" as const;
  if (status === "HIGH" || status === "CRITICAL") return "danger" as const;
  return "neutral" as const;
}

export function InvoiceDetailDrawer({
  invoice,
  open,
  onClose,
}: {
  invoice: Invoice | null;
  open: boolean;
  onClose: () => void;
}) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [summary, setSummary] = useState<string>("");
  const [promises, setPromises] = useState<PaymentPromise[]>([]);
  const [openInvoices, setOpenInvoices] = useState<Invoice[]>([]);

  useEffect(() => {
    if (!open || !invoice) return;
    let cancelled = false;
    void (async () => {
      const [cRes, sRes, pRes, iRes] = await Promise.all([
        getCustomer(invoice.customer),
        fetchCustomerSummary(invoice.customer),
        listPaymentPromises({ customer: invoice.customer, page_size: 5 }),
        listInvoices({
          customer: invoice.customer,
          status: "OPEN,OVERDUE,PARTIALLY_PAID",
          page_size: 5,
        }),
      ]);
      if (cancelled) return;
      if (cRes.ok) setCustomer(cRes.data);
      if (sRes.ok) setSummary(sRes.data.summary || "");
      if (pRes.ok) setPromises(pRes.data.results || []);
      if (iRes.ok) setOpenInvoices(iRes.data.results || []);
    })();
    return () => {
      cancelled = true;
    };
  }, [open, invoice]);

  if (!invoice) return null;

  const risk = (customer?.risk_status || invoice.customer_risk_status || "MEDIUM") as RiskStatus;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={invoice.customer_name}
      side="right"
      className="w-[min(28rem,96vw)]"
      footer={
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/customers/${invoice.customer}`}
            className="inline-flex h-9 items-center rounded-[var(--radius-md)] bg-primary px-3 text-xs font-semibold text-primary-foreground"
          >
            Müşteri sayfası
          </Link>
          <Link
            href={`/invoices/${invoice.id}`}
            className="inline-flex h-9 items-center rounded-[var(--radius-md)] border border-border-default px-3 text-xs font-semibold"
          >
            Fatura detayı
          </Link>
          <a
            href={invoice.customer_phone ? `tel:${invoice.customer_phone}` : `/collections?customer=${invoice.customer}`}
            className="inline-flex h-9 items-center rounded-[var(--radius-md)] border border-border-default px-3 text-xs font-semibold"
          >
            Ara
          </a>
          <Link
            href={`/promises?create=1&customer=${invoice.customer}`}
            className="inline-flex h-9 items-center rounded-[var(--radius-md)] border border-border-default px-3 text-xs font-semibold"
          >
            Ödeme sözü
          </Link>
        </div>
      }
    >
      <div className="space-y-5">
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-subtle">Müşteri özeti</h3>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StatusChip tone={riskTone(risk)} label={RISK_LABELS[risk] ?? risk} />
            {customer?.code ? <span className="text-xs text-muted">{customer.code}</span> : null}
          </div>
          <p className="mt-2 text-sm text-muted">{summary || "Özet yükleniyor…"}</p>
        </section>

        <section className="grid grid-cols-2 gap-3">
          <Metric label="Açık bakiye" value={customer ? formatMoney(customer.open_balance) : "—"} />
          <Metric
            label="Gecikmiş"
            value={customer ? formatMoney(customer.overdue_balance) : "—"}
          />
          <Metric
            label="Son görüşme"
            value={
              customer?.last_contact_at
                ? formatDate(customer.last_contact_at.slice(0, 10))
                : "—"
            }
          />
          <Metric label="Bu fatura kalan" value={<Money value={invoice.remaining_amount} currency={invoice.currency} size="table" />} />
        </section>

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-subtle">Ödeme sözleri</h3>
          {promises.length === 0 ? (
            <p className="mt-2 text-sm text-muted">Aktif söz yok.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {promises.map((p) => (
                <li key={p.id} className="rounded-[var(--radius-md)] bg-surface-secondary px-3 py-2 text-sm">
                  {formatMoney(p.amount, p.currency)} · {formatDate(p.promised_date)} · {p.status}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-subtle">Açık faturalar</h3>
          <ul className="mt-2 space-y-2">
            {openInvoices.map((inv) => (
              <li key={inv.id} className="flex justify-between gap-2 text-sm">
                <Link href={`/invoices/${inv.id}`} className="font-medium text-primary hover:underline">
                  {inv.number}
                </Link>
                <span className="text-muted">
                  <Money value={inv.remaining_amount} currency={inv.currency} size="table" />
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </Drawer>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-border-default px-3 py-2">
      <p className="text-[11px] text-subtle">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}
