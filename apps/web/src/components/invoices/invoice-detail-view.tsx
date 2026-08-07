"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { cancelInvoice, getInvoice } from "@/lib/invoices/api";
import { INVOICE_STATUS_LABELS, type Invoice, type InvoiceStatus } from "@/lib/invoices/types";
import type { AppError } from "@/lib/errors";
import { cn } from "@/lib/cn";

type TabId = "info" | "allocations" | "tasks" | "promises" | "contacts" | "audit";

const TABS: { id: TabId; label: string }[] = [
  { id: "info", label: "Fatura bilgileri" },
  { id: "allocations", label: "Ödeme dağılımları" },
  { id: "tasks", label: "Tahsilat görevleri" },
  { id: "promises", label: "Ödeme sözleri" },
  { id: "contacts", label: "İletişim geçmişi" },
  { id: "audit", label: "Audit log" },
];

function statusTone(status: InvoiceStatus) {
  if (status === "PAID") return "success" as const;
  if (status === "OPEN") return "brand" as const;
  if (status === "PARTIALLY_PAID") return "warning" as const;
  if (status === "OVERDUE") return "danger" as const;
  return "neutral" as const;
}

export function InvoiceDetailView({ invoiceId }: { invoiceId: number }) {
  const router = useRouter();
  const { toast } = useToast();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [tab, setTab] = useState<TabId>("info");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const load = useCallback(async () => {
    const result = await getInvoice(invoiceId);
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      setInvoice(null);
      return;
    }
    setError(null);
    setInvoice(result.data);
  }, [invoiceId]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      const result = await getInvoice(invoiceId);
      if (cancelled) return;
      setLoading(false);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setInvoice(result.data);
    });
    return () => {
      cancelled = true;
    };
  }, [invoiceId]);

  const onCancel = async () => {
    setCancelling(true);
    const result = await cancelInvoice(invoiceId);
    setCancelling(false);
    setConfirmOpen(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "Fatura iptal edildi", tone: "success" });
    setInvoice(result.data);
  };

  if (loading) return <LoadingSkeleton lines={8} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!invoice) return null;

  const allocations = invoice.payment_allocations ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-serif text-3xl tracking-tight text-slate-900">{invoice.number}</h1>
            <Badge tone={statusTone(invoice.status)}>{INVOICE_STATUS_LABELS[invoice.status]}</Badge>
          </div>
          <p className="text-sm text-slate-600">
            <Link href={`/customers/${invoice.customer}`} className="text-brand hover:underline">
              {invoice.customer_name}
            </Link>
            {" · "}
            Sorumlu: {invoice.assigned_user_name || "—"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {invoice.status !== "CANCELLED" && invoice.status !== "PAID" ? (
            <Button variant="danger" onClick={() => setConfirmOpen(true)}>
              İptal et
            </Button>
          ) : null}
          <Button variant="outline" onClick={() => router.push("/invoices")}>
            Listeye dön
          </Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="Toplam" value={formatMoney(invoice.total_amount, invoice.currency)} />
        <SummaryCard
          label="Ödenen"
          value={formatMoney(invoice.allocated_amount, invoice.currency)}
        />
        <SummaryCard
          label="Kalan bakiye"
          value={formatMoney(invoice.remaining_amount, invoice.currency)}
        />
        <SummaryCard
          label="Gecikme"
          value={
            invoice.status === "PAID"
              ? invoice.actual_delay_days == null
                ? "—"
                : `${invoice.actual_delay_days} gün`
              : `${invoice.overdue_days} gün`
          }
        />
      </div>

      {invoice.collection_outlook &&
      invoice.collection_outlook.probability_30d != null ? (
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">Tahsilat olasılığı</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryCard
              label="7 gün içinde"
              value={formatPct(invoice.collection_outlook.probability_7d)}
            />
            <SummaryCard
              label="30 gün içinde"
              value={formatPct(invoice.collection_outlook.probability_30d)}
            />
            <SummaryCard
              label="60 gün içinde"
              value={formatPct(invoice.collection_outlook.probability_60d)}
            />
            <SummaryCard
              label="Beklenen tahsilat"
              value={formatDate(invoice.collection_outlook.expected_collection_date)}
            />
          </div>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition",
              tab === item.id
                ? "bg-brand/10 text-brand"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "info" ? (
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <Info label="Fatura no" value={invoice.number} />
            <Info label="Müşteri" value={invoice.customer_name} />
            <Info label="Fatura tarihi" value={formatDate(invoice.invoice_date)} />
            <Info label="Vade tarihi" value={formatDate(invoice.due_date)} />
            <Info label="Para birimi" value={invoice.currency} />
            <Info
              label="Ara toplam"
              value={formatMoney(invoice.subtotal_amount, invoice.currency)}
            />
            <Info label="Vergi" value={formatMoney(invoice.tax_amount, invoice.currency)} />
            <Info label="Toplam" value={formatMoney(invoice.total_amount, invoice.currency)} />
            <Info label="Ödeme tamamlanma" value={formatDate(invoice.payment_completion_date)} />
            <Info
              label="Risk gecikme günü"
              value={
                invoice.delay_days_for_risk == null ? "—" : `${invoice.delay_days_for_risk} gün`
              }
            />
            <div className="sm:col-span-2">
              <Info label="Açıklama" value={invoice.description || "—"} />
            </div>
          </dl>
        </section>
      ) : null}

      {tab === "allocations" ? (
        allocations.length === 0 ? (
          <EmptyState
            title="Ödeme dağılımı yok"
            description="Ödeme modülü tamamlandığında burada görünecek."
          />
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                <tr>
                  <th className="px-4 py-3">Ödeme</th>
                  <th className="px-4 py-3">Tarih</th>
                  <th className="px-4 py-3 text-right">Tutar</th>
                </tr>
              </thead>
              <tbody>
                {allocations.map((row) => (
                  <tr key={row.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-3">#{row.payment_id ?? row.id}</td>
                    <td className="px-4 py-3">{formatDate(row.payment_date)}</td>
                    <td className="px-4 py-3 text-right">
                      {formatMoney(row.amount, invoice.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : null}

      {tab === "tasks" ? (
        <EmptyState
          title="Tahsilat görevi yok"
          description="Görev modülü sonraki epic’te gelecek."
        />
      ) : null}
      {tab === "promises" ? (
        <EmptyState title="Ödeme sözü yok" description="Söz modülü sonraki epic’te gelecek." />
      ) : null}
      {tab === "contacts" ? (
        <EmptyState
          title="İletişim geçmişi yok"
          description="Aktivite kayıtları sonraki epic’te gelecek."
        />
      ) : null}
      {tab === "audit" ? (
        <EmptyState title="Audit kaydı yok" description="Audit log sonraki epic’te gelecek." />
      ) : null}

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => void onCancel()}
        title="Faturayı iptal et"
        description="Fatura CANCELLED durumuna alınacak. Devam edilsin mi?"
        confirmLabel="İptal et"
        danger
        loading={cancelling}
      />
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function formatPct(value: string | null | undefined) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return "—";
  return `%${Math.round(n * 100)}`;
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900">{value}</dd>
    </div>
  );
}
