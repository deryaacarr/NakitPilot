"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { CustomerAssistantSummary } from "@/components/customers/customer-assistant-summary";
import { CustomerPaymentPlanSuggestions } from "@/components/customers/customer-payment-plan-suggestions";
import { CustomerCommunicationPanel } from "@/components/customers/customer-communication-panel";
import { CustomerContactsPanel } from "@/components/customers/customer-contacts-panel";
import { CustomerDisputesPanel } from "@/components/customers/customer-disputes-panel";
import { CustomerRiskExplanation } from "@/components/customers/customer-risk-explanation";
import { CustomerRiskHistoryChart } from "@/components/customers/customer-risk-history";
import { CustomerTimeline } from "@/components/customers/customer-timeline";
import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { deactivateCustomer, getCustomer } from "@/lib/customers/api";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { RISK_LABELS, type Customer, type RiskStatus } from "@/lib/customers/types";
import type { AppError } from "@/lib/errors";
import { cn } from "@/lib/cn";
import { useRouter } from "next/navigation";

type TabId =
  | "summary"
  | "invoices"
  | "payments"
  | "collections"
  | "promises"
  | "tasks"
  | "disputes"
  | "notes";

const TABS: { id: TabId; label: string }[] = [
  { id: "summary", label: "Özet" },
  { id: "invoices", label: "Faturalar" },
  { id: "payments", label: "Ödemeler" },
  { id: "collections", label: "Tahsilat geçmişi" },
  { id: "promises", label: "Ödeme sözleri" },
  { id: "tasks", label: "Görevler" },
  { id: "disputes", label: "İtirazlar" },
  { id: "notes", label: "Notlar" },
];

function riskTone(status: RiskStatus) {
  if (status === "LOW") return "success" as const;
  if (status === "MEDIUM") return "warning" as const;
  if (status === "HIGH" || status === "CRITICAL") return "danger" as const;
  return "neutral" as const;
}

export function CustomerDetailView({ customerId }: { customerId: number }) {
  const router = useRouter();
  const { toast } = useToast();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [tab, setTab] = useState<TabId>("summary");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deactivating, setDeactivating] = useState(false);

  const load = useCallback(async () => {
    const result = await getCustomer(customerId);
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      setCustomer(null);
      return;
    }
    setError(null);
    setCustomer(result.data);
  }, [customerId]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      const result = await getCustomer(customerId);
      if (cancelled) return;
      setLoading(false);
      if (!result.ok) {
        setError(result.error);
        setCustomer(null);
        return;
      }
      setError(null);
      setCustomer(result.data);
    });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  const onDeactivate = async () => {
    setDeactivating(true);
    const result = await deactivateCustomer(customerId);
    setDeactivating(false);
    setConfirmOpen(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "Müşteri pasife alındı", tone: "success" });
    setCustomer(result.data);
  };

  if (loading) return <LoadingSkeleton lines={8} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!customer) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-serif text-3xl tracking-tight text-slate-900">{customer.name}</h1>
            <Badge tone={riskTone(customer.risk_status)}>{RISK_LABELS[customer.risk_status]}</Badge>
            {!customer.is_active ? <Badge tone="neutral">Pasif</Badge> : null}
          </div>
          <p className="text-sm text-slate-600">
            Kod: {customer.code || "—"} · Sorumlu: {customer.assigned_user_name || "—"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/customers/${customer.id}/edit`}
            className="border-brand text-brand inline-flex h-10 items-center rounded-lg border px-4 text-sm font-semibold hover:bg-teal-50"
          >
            Düzenle
          </Link>
          {customer.is_active ? (
            <Button variant="danger" onClick={() => setConfirmOpen(true)}>
              Pasife al
            </Button>
          ) : null}
          <Button variant="outline" onClick={() => router.push("/customers")}>
            Listeye dön
          </Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <SummaryCard label="Normal açık bakiye" value={formatMoney(customer.open_balance)} />
        <SummaryCard label="Gecikmiş açık bakiye" value={formatMoney(customer.overdue_balance)} />
        <SummaryCard
          label="İtirazlı bakiye"
          value={formatMoney(customer.disputed_balance ?? "0")}
        />
        <SummaryCard
          label="En eski gecikme"
          value={customer.oldest_overdue_days == null ? "—" : `${customer.oldest_overdue_days} gün`}
        />
        <SummaryCard label="Risk skoru" value={String(customer.risk_score)} />
        <SummaryCard
          label="Ortalama ödeme gecikmesi"
          value={customer.avg_delay_days == null ? "—" : `${customer.avg_delay_days} gün`}
        />
      </div>

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

      {tab === "summary" ? (
        <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-900">Genel</h2>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <Info label="Vergi / TCKN" value={customer.tax_number || "—"} />
                <Info label="E-posta" value={customer.email || "—"} />
                <Info label="Telefon" value={customer.phone || "—"} />
                <Info label="Şehir" value={customer.city || "—"} />
                <Info label="Sektör" value={customer.sector || "—"} />
                <Info label="Vade" value={`${customer.payment_term_days} gün`} />
                <Info label="Kredi limiti" value={formatMoney(customer.credit_limit)} />
                <Info label="Son iletişim" value={formatDate(customer.last_contact_at)} />
              </dl>
            </section>
            <section className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-semibold text-slate-900">İletişim kişileri</h2>
              <CustomerContactsPanel customerId={customer.id} />
            </section>
            <section className="rounded-xl border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-semibold text-slate-900">İletişim tercihleri</h2>
              <CustomerCommunicationPanel customerId={customer.id} />
            </section>
          </div>
          <CustomerAssistantSummary customerId={customer.id} />
          <CustomerPaymentPlanSuggestions customerId={customer.id} />
          <CustomerRiskExplanation customerId={customer.id} />
          <CustomerRiskHistoryChart customerId={customer.id} />
        </div>
      ) : null}

      {tab === "notes" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm whitespace-pre-wrap text-slate-700">
            {customer.notes || "Not bulunmuyor."}
          </p>
        </div>
      ) : null}

      {tab === "collections" ? <CustomerTimeline customerId={customer.id} /> : null}

      {tab === "disputes" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">İtiraz ve uyuşmazlıklar</h2>
          <CustomerDisputesPanel customerId={customer.id} />
        </div>
      ) : null}

      {tab !== "summary" &&
      tab !== "notes" &&
      tab !== "collections" &&
      tab !== "disputes" ? (
        <EmptyState
          title="Yakında"
          description="Bu sekme ilgili modül (fatura / ödeme / tahsilat) tamamlandığında dolacak."
        />
      ) : null}

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => void onDeactivate()}
        title="Müşteriyi pasife al"
        description="Kayıt silinmez; is_active=false yapılır. Devam edilsin mi?"
        confirmLabel="Pasife al"
        danger
        loading={deactivating}
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

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900">{value}</dd>
    </div>
  );
}
