"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Surface } from "@/components/ui/surface";
import {
  cancelSubscription,
  confirmCheckout,
  fetchBillingInvoices,
  fetchPlans,
  fetchSubscription,
  fetchTrial,
  scheduleDowngrade,
  startCheckout,
  updatePaymentMethod,
  type BillingInvoice,
  type SubscriptionMe,
  type SubscriptionPlan,
  type TrialProgress,
} from "@/lib/billing/api";
import { getAccessToken } from "@/lib/auth/storage";
import { env } from "@/lib/env";
import { getOrganizationId } from "@/lib/api/organization";
import { cn } from "@/lib/cn";

export function SubscriptionPanel() {
  const [sub, setSub] = useState<SubscriptionMe | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [trial, setTrial] = useState<TrialProgress | null>(null);
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [last4, setLast4] = useState("4242");
  const [brand, setBrand] = useState("visa");

  const reload = useCallback(async () => {
    const [s, p, t, inv] = await Promise.all([
      fetchSubscription(),
      fetchPlans(),
      fetchTrial(),
      fetchBillingInvoices(),
    ]);
    if (!s.ok) {
      setError(s.error.message);
      return;
    }
    setSub(s.data);
    if (p.ok) setPlans(p.data.results);
    if (t.ok) setTrial(t.data);
    if (inv.ok) setInvoices(inv.data.results);
    setError(null);
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function upgrade(code: string) {
    setBusy(true);
    const checkout = await startCheckout(code);
    if (!checkout.ok) {
      setError(checkout.error.message);
      setBusy(false);
      return;
    }
    const confirmed = await confirmCheckout(checkout.data.checkout_id, code);
    if (!confirmed.ok) {
      setError(confirmed.error.message);
      setBusy(false);
      return;
    }
    await reload();
    setBusy(false);
  }

  async function downgrade(code: string) {
    setBusy(true);
    const result = await scheduleDowngrade(code);
    if (!result.ok) setError(result.error.message);
    else await reload();
    setBusy(false);
  }

  async function savePaymentMethod() {
    setBusy(true);
    const result = await updatePaymentMethod(brand, last4);
    if (!result.ok) setError(result.error.message);
    else await reload();
    setBusy(false);
  }

  async function onCancel() {
    setBusy(true);
    const result = await cancelSubscription(true);
    if (!result.ok) setError(result.error.message);
    else await reload();
    setBusy(false);
  }

  async function downloadInvoice(id: number, number: string) {
    const token = getAccessToken();
    const org = getOrganizationId();
    const base = env.apiUrl.replace(/\/$/, "");
    const res = await fetch(`${base}/api/billing/invoices/${id}/download/`, {
      headers: {
        Authorization: token ? `Bearer ${token}` : "",
        "X-Organization-Id": org ? String(org) : "",
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      setError("Fatura indirilemedi.");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${number}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!sub && !error) {
    return (
      <Surface as="section" id="subscription">
        <p className="text-sm text-muted">Abonelik yükleniyor…</p>
      </Surface>
    );
  }

  return (
    <Surface as="section" id="subscription" className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Abonelik ve kullanım</h2>
        <p className="mt-1 text-xs text-muted">
          Paket, limitler, yükseltme/düşürme, ödeme yöntemi ve faturalar.
        </p>
      </div>
      {error ? <p className="text-sm text-danger-foreground">{error}</p> : null}
      {sub ? (
        <>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <Item label="Paket" value={`${sub.plan.name} (${sub.plan.code})`} />
            <Item label="Durum" value={sub.status} />
            <Item label="Aylık ücret" value={`₺${sub.plan.price_monthly}`} />
            <Item label="Salt okunur" value={sub.read_only ? "Evet" : "Hayır"} />
            <Item
              label="Ödeme yöntemi"
              value={
                sub.payment_method.last4
                  ? `${sub.payment_method.brand} •••• ${sub.payment_method.last4}`
                  : "Tanımlı değil"
              }
            />
            <Item
              label="Planlanan düşürme"
              value={
                sub.scheduled_plan
                  ? `${sub.scheduled_plan.name} (${sub.scheduled_plan_at ?? "dönem sonu"})`
                  : "—"
              }
            />
          </dl>

          {trial && trial.status === "TRIALING" ? (
            <div className="rounded-[var(--radius-md)] border border-warning/30 bg-warning-soft/80 p-3">
              <p className="text-sm font-medium text-warning-foreground">
                Ücretsiz deneme — {trial.days_left ?? "—"} gün kaldı (kart gerekmez)
              </p>
              <ul className="mt-2 space-y-1 text-sm text-warning-foreground/90">
                {trial.steps.map((s) => (
                  <li key={s.key}>
                    {s.done ? "✓" : "○"} {s.label}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-subtle">
              Kullanım limitleri
            </h3>
            <ul className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
              {Object.entries(sub.usage.metrics).map(([key, value]) => (
                <li
                  key={key}
                  className="flex justify-between gap-2 border-b border-border-default py-1"
                >
                  <span className="text-muted">{sub.usage.labels[key] ?? key}</span>
                  <span className="tabular-nums text-foreground">
                    {value}
                    {sub.usage.limits[key] != null ? ` / ${sub.usage.limits[key]}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-subtle">Paketler</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {plans.map((p) => {
                const current = p.code === sub.plan.code;
                const currentPlan = plans.find((x) => x.code === sub.plan.code);
                const currentOrder = currentPlan?.sort_order ?? 0;
                const isUpgrade = p.sort_order > currentOrder;
                return (
                  <button
                    key={p.code}
                    type="button"
                    disabled={busy || current}
                    onClick={() => void (isUpgrade ? upgrade(p.code) : downgrade(p.code))}
                    className={cn(
                      "min-h-11 rounded-[var(--radius-md)] border px-3 py-2 text-left text-sm transition disabled:opacity-50",
                      current
                        ? "border-primary/40 bg-primary/10 text-foreground"
                        : "border-border-default bg-surface-secondary text-foreground hover:border-border-strong",
                    )}
                  >
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-muted">₺{p.price_monthly}/ay</div>
                    <div className="mt-1 text-xs text-muted">
                      {current ? "Mevcut" : isUpgrade ? "Yükselt" : "Düşürmeyi planla"}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-[8rem]">
              <Input
                label="Kart markası"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
              />
            </div>
            <div className="w-28">
              <Input
                label="Son 4 hane"
                value={last4}
                maxLength={4}
                onChange={(e) => setLast4(e.target.value.replace(/\D/g, "").slice(0, 4))}
              />
            </div>
            <Button type="button" disabled={busy} onClick={() => void savePaymentMethod()}>
              Ödeme yöntemini kaydet
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy || sub.cancel_at_period_end}
              className="border-danger/40 text-danger-foreground"
              onClick={() => void onCancel()}
            >
              {sub.cancel_at_period_end ? "İptal planlandı" : "Aboneliği iptal et"}
            </Button>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-subtle">Faturalar</h3>
            {invoices.length === 0 ? (
              <p className="mt-2 text-sm text-muted">Henüz fatura yok.</p>
            ) : (
              <ul className="mt-2 divide-y divide-border-default text-sm">
                {invoices.map((inv) => (
                  <li key={inv.id} className="flex items-center justify-between py-2">
                    <span className="text-foreground">
                      {inv.number} · {inv.status} · {inv.currency} {inv.total}
                    </span>
                    <button
                      type="button"
                      className="min-h-11 text-primary underline"
                      onClick={() => void downloadInvoice(inv.id, inv.number)}
                    >
                      İndir
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : null}
    </Surface>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-medium text-foreground">{value}</dd>
    </div>
  );
}
