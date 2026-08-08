"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { CustomerAssistantSummary } from "@/components/customers/customer-assistant-summary";
import { CustomerCommunicationPanel } from "@/components/customers/customer-communication-panel";
import { CustomerContactsPanel } from "@/components/customers/customer-contacts-panel";
import { CustomerDisputesPanel } from "@/components/customers/customer-disputes-panel";
import { CustomerFinancialSummaryPanel } from "@/components/customers/customer-financial-summary";
import { CustomerHealthScore } from "@/components/customers/customer-health-score";
import { CustomerPaymentPlanSuggestions } from "@/components/customers/customer-payment-plan-suggestions";
import { CustomerQuickActions } from "@/components/customers/customer-quick-actions";
import { CustomerRiskHistoryChart } from "@/components/customers/customer-risk-history";
import { CustomerTimeline } from "@/components/customers/customer-timeline";
import { ErrorState } from "@/components/errors";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { DetailSkeleton, LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { EMPTY_PRESETS } from "@/lib/ui/empty-presets";
import { Money } from "@/components/ui/money";
import { StatusChip } from "@/components/ui/status-chip";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";
import { deactivateCustomer, getCustomer } from "@/lib/customers/api";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { RISK_LABELS, type Customer, type RiskStatus } from "@/lib/customers/types";
import type { SemanticTone } from "@/lib/design/semantic";
import type { AppError } from "@/lib/errors";
import { listInvoices } from "@/lib/invoices/api";
import { listPayments } from "@/lib/payments/api";
import { listPaymentPromises } from "@/lib/promises/api";
import { listCollectionTasks } from "@/lib/collections/api";

type TabId =
  | "summary"
  | "finance"
  | "timeline"
  | "invoices"
  | "payments"
  | "promises"
  | "tasks"
  | "disputes"
  | "notes";

const TABS: { id: TabId; label: string }[] = [
  { id: "summary", label: "Özet" },
  { id: "finance", label: "Finansal özet" },
  { id: "timeline", label: "Zaman çizelgesi" },
  { id: "invoices", label: "Faturalar" },
  { id: "payments", label: "Ödemeler" },
  { id: "promises", label: "Ödeme sözleri" },
  { id: "tasks", label: "Görevler" },
  { id: "disputes", label: "İtirazlar" },
  { id: "notes", label: "Notlar" },
];

function riskTone(status: RiskStatus): SemanticTone {
  if (status === "LOW") return "success";
  if (status === "MEDIUM") return "warning";
  if (status === "HIGH" || status === "CRITICAL") return "danger";
  return "neutral";
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
  const [timelineKey, setTimelineKey] = useState(0);

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
    setLoading(true);
    void load();
  }, [load]);

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

  if (loading) return <DetailSkeleton />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!customer) return null;

  return (
    <div className="space-y-6 pb-20">
      {/* NP-410 header */}
      <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-serif text-3xl tracking-tight text-foreground">{customer.name}</h1>
              <StatusChip
                tone={riskTone(customer.risk_status)}
                label={RISK_LABELS[customer.risk_status]}
              />
              {!customer.is_active ? <StatusChip tone="neutral" label="Pasif" /> : null}
            </div>
            <p className="text-sm text-muted">
              Kod: {customer.code || "—"} · {customer.phone || customer.email || "İletişim yok"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/customers/${customer.id}/edit`}
              className="inline-flex h-10 items-center rounded-[var(--radius-md)] border border-primary px-4 text-sm font-semibold text-primary"
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

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Toplam açık bakiye" value={<Money value={customer.open_balance} />} />
          <Metric label="Gecikmiş bakiye" value={<Money value={customer.overdue_balance} />} />
          <Metric
            label="Ortalama gecikme"
            value={customer.avg_delay_days == null ? "—" : `${customer.avg_delay_days} gün`}
          />
          <Metric
            label="Son ödeme"
            value={
              customer.last_payment_date
                ? `${formatDate(customer.last_payment_date)}${
                    customer.last_payment_amount
                      ? ` · ${formatMoney(customer.last_payment_amount, customer.last_payment_currency || "TRY")}`
                      : ""
                  }`
                : "—"
            }
          />
          <Metric label="Sorumlu kullanıcı" value={customer.assigned_user_name || "—"} />
          <Metric
            label="En eski gecikme"
            value={
              customer.oldest_overdue_days == null ? "—" : `${customer.oldest_overdue_days} gün`
            }
          />
          <Metric label="Risk skoru" value={`${customer.risk_score} / 100`} />
          <Metric
            label="İtirazlı bakiye"
            value={formatMoney(customer.disputed_balance ?? "0")}
          />
        </div>

        <div className="mt-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">
            Hızlı aksiyonlar
          </p>
          <CustomerQuickActions
            customer={customer}
            onNoteAdded={() => {
              setTimelineKey((k) => k + 1);
              if (tab !== "timeline") setTab("timeline");
            }}
          />
        </div>
      </section>

      <div className="flex flex-wrap gap-2 border-b border-border-default pb-2">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={cn(
              "rounded-[var(--radius-md)] px-3 py-1.5 text-sm font-medium transition",
              tab === item.id
                ? "bg-primary/10 text-primary"
                : "text-muted hover:bg-surface-tertiary hover:text-foreground",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "summary" ? (
        <div className="space-y-4">
          <CustomerHealthScore customerId={customer.id} />
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="space-y-3 rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
              <h2 className="text-sm font-semibold text-foreground">Genel</h2>
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
            <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
              <h2 className="mb-3 text-sm font-semibold">İletişim kişileri</h2>
              <CustomerContactsPanel customerId={customer.id} />
            </section>
            <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
              <h2 className="mb-3 text-sm font-semibold">İletişim tercihleri</h2>
              <CustomerCommunicationPanel customerId={customer.id} />
            </section>
            <CustomerRiskHistoryChart customerId={customer.id} />
          </div>
          <CustomerAssistantSummary customerId={customer.id} />
          <CustomerPaymentPlanSuggestions customerId={customer.id} />
        </div>
      ) : null}

      {tab === "finance" ? <CustomerFinancialSummaryPanel customerId={customer.id} /> : null}

      {tab === "timeline" ? (
        <CustomerTimeline customerId={customer.id} refreshKey={timelineKey} />
      ) : null}

      {tab === "notes" ? (
        <div className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
          <p className="whitespace-pre-wrap text-sm text-foreground">
            {customer.notes || "Not bulunmuyor."}
          </p>
        </div>
      ) : null}

      {tab === "disputes" ? (
        <div className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
          <CustomerDisputesPanel customerId={customer.id} />
        </div>
      ) : null}

      {tab === "invoices" ? <RelatedInvoices customerId={customer.id} /> : null}
      {tab === "payments" ? <RelatedPayments customerId={customer.id} /> : null}
      {tab === "promises" ? <RelatedPromises customerId={customer.id} /> : null}
      {tab === "tasks" ? <RelatedTasks customerId={customer.id} /> : null}

      {/* NP-414 sticky actions */}
      <CustomerQuickActions
        customer={customer}
        sticky
        onNoteAdded={() => {
          setTimelineKey((k) => k + 1);
          setTab("timeline");
        }}
      />

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

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-border-default bg-surface-secondary/50 px-3 py-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-subtle">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted">{label}</dt>
      <dd className="font-medium text-foreground">{value}</dd>
    </div>
  );
}

function RelatedInvoices({ customerId }: { customerId: number }) {
  const [rows, setRows] = useState<Array<{ id: number; number: string; remaining_amount: string; status: string; due_date: string; currency: string }>>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    void listInvoices({ customer: customerId, page_size: 20 }).then((res) => {
      setLoading(false);
      if (res.ok) setRows(res.data.results);
    });
  }, [customerId]);
  if (loading) return <LoadingSkeleton lines={4} />;
  if (!rows.length) {
    return (
      <EmptyState
        title={EMPTY_PRESETS.invoices.title}
        description="Bu müşteriye ait fatura bulunamadı."
        why={EMPTY_PRESETS.invoices.why}
        actionLabel={EMPTY_PRESETS.invoices.actionLabel}
        actionHref={EMPTY_PRESETS.invoices.actionHref}
      />
    );
  }
  return (
    <ul className="divide-y divide-border-default rounded-[var(--radius-lg)] border border-border-default bg-surface-primary">
      {rows.map((r) => (
        <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
          <Link href={`/invoices/${r.id}`} className="font-medium text-primary hover:underline">
            {r.number}
          </Link>
          <span className="text-muted">{formatDate(r.due_date)} · {r.status}</span>
          <Money value={r.remaining_amount} currency={r.currency} size="table" />
        </li>
      ))}
    </ul>
  );
}

function RelatedPayments({ customerId }: { customerId: number }) {
  const [rows, setRows] = useState<Array<{ id: number; amount: string; payment_date: string; currency: string; reference: string }>>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    void listPayments({ customer: customerId, page_size: 20 }).then((res) => {
      setLoading(false);
      if (res.ok) setRows(res.data.results);
    });
  }, [customerId]);
  if (loading) return <LoadingSkeleton lines={4} />;
  if (!rows.length) {
    return (
      <EmptyState
        title={EMPTY_PRESETS.payments.title}
        description="Bu müşteriye ait ödeme bulunamadı."
        why={EMPTY_PRESETS.payments.why}
        actionLabel={EMPTY_PRESETS.payments.actionLabel}
        actionHref={EMPTY_PRESETS.payments.actionHref}
      />
    );
  }
  return (
    <ul className="divide-y divide-border-default rounded-[var(--radius-lg)] border border-border-default bg-surface-primary">
      {rows.map((r) => (
        <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
          <span className="font-medium">{formatDate(r.payment_date)}</span>
          <span className="text-muted">{r.reference || "—"}</span>
          <Money value={r.amount} currency={r.currency} size="table" />
        </li>
      ))}
    </ul>
  );
}

function RelatedPromises({ customerId }: { customerId: number }) {
  const [rows, setRows] = useState<Array<{ id: number; amount: string; promised_date: string; status: string; currency: string }>>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    void listPaymentPromises({ customer: customerId, page_size: 20 }).then((res) => {
      setLoading(false);
      if (res.ok) setRows(res.data.results);
    });
  }, [customerId]);
  if (loading) return <LoadingSkeleton lines={4} />;
  if (!rows.length) {
    return (
      <EmptyState
        title={EMPTY_PRESETS.promises.title}
        description="Bu müşteriye ait söz bulunamadı."
        why={EMPTY_PRESETS.promises.why}
        actionLabel={EMPTY_PRESETS.promises.actionLabel}
        actionHref={EMPTY_PRESETS.promises.actionHref}
      />
    );
  }
  return (
    <ul className="divide-y divide-border-default rounded-[var(--radius-lg)] border border-border-default bg-surface-primary">
      {rows.map((r) => (
        <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
          <span className="font-medium">{formatDate(r.promised_date)}</span>
          <span className="text-muted">{r.status}</span>
          <Money value={r.amount} currency={r.currency} size="table" />
        </li>
      ))}
    </ul>
  );
}

function RelatedTasks({ customerId }: { customerId: number }) {
  const [rows, setRows] = useState<Array<{ id: number; title: string; due_date: string; status: string }>>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    void listCollectionTasks({ customer: customerId, page_size: 20 }).then((res) => {
      setLoading(false);
      if (res.ok) setRows(res.data.results);
    });
  }, [customerId]);
  if (loading) return <LoadingSkeleton lines={4} />;
  if (!rows.length) return <EmptyState title="Görev yok" description="Bu müşteriye ait görev bulunamadı." />;
  return (
    <ul className="divide-y divide-border-default rounded-[var(--radius-lg)] border border-border-default bg-surface-primary">
      {rows.map((r) => (
        <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
          <span className="font-medium">{r.title}</span>
          <span className="text-muted">{formatDate(r.due_date)}</span>
          <span>{r.status}</span>
        </li>
      ))}
    </ul>
  );
}
