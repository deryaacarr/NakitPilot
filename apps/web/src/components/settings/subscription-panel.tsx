"use client";

import { useCallback, useEffect, useState } from "react";

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
      <section id="billing" className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-sm text-slate-500">Abonelik yükleniyor…</p>
      </section>
    );
  }

  return (
    <section id="billing" className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">Abonelik ve kullanım</h2>
        <p className="mt-1 text-xs text-slate-500">
          Paket, limitler, yükseltme/düşürme, ödeme yöntemi ve faturalar.
        </p>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {sub ? (
        <>
          <dl className="grid gap-3 sm:grid-cols-2 text-sm">
            <Item label="Paket" value={`${sub.plan.name} (${sub.plan.code})`} />
            <Item label="Durum" value={sub.status} />
            <Item label="Aylık ücret" value={`₺${sub.plan.price_monthly}`} />
            <Item
              label="Salt okunur"
              value={sub.read_only ? "Evet" : "Hayır"}
            />
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
            <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3">
              <p className="text-sm font-medium text-amber-900">
                Ücretsiz deneme — {trial.days_left ?? "—"} gün kaldı (kart gerekmez)
              </p>
              <ul className="mt-2 space-y-1 text-sm text-amber-900/90">
                {trial.steps.map((s) => (
                  <li key={s.key}>
                    {s.done ? "✓" : "○"} {s.label}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Kullanım limitleri
            </h3>
            <ul className="mt-2 grid gap-2 sm:grid-cols-2 text-sm">
              {Object.entries(sub.usage.metrics).map(([key, value]) => (
                <li key={key} className="flex justify-between gap-2 border-b border-slate-100 py-1">
                  <span className="text-slate-600">{sub.usage.labels[key] ?? key}</span>
                  <span className="tabular-nums text-slate-900">
                    {value}
                    {sub.usage.limits[key] != null ? ` / ${sub.usage.limits[key]}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Paketler</h3>
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
                    className="rounded-lg border border-slate-200 px-3 py-2 text-left text-sm hover:border-slate-400 disabled:opacity-50"
                  >
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-slate-500">₺{p.price_monthly}/ay</div>
                    <div className="mt-1 text-xs text-slate-600">
                      {current ? "Mevcut" : isUpgrade ? "Yükselt" : "Düşürmeyi planla"}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <label className="text-sm">
              Kart markası
              <input
                className="mt-1 block rounded border border-slate-200 px-2 py-1"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
              />
            </label>
            <label className="text-sm">
              Son 4 hane
              <input
                className="mt-1 block w-24 rounded border border-slate-200 px-2 py-1"
                value={last4}
                maxLength={4}
                onChange={(e) => setLast4(e.target.value.replace(/\D/g, "").slice(0, 4))}
              />
            </label>
            <button
              type="button"
              disabled={busy}
              onClick={() => void savePaymentMethod()}
              className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50"
            >
              Ödeme yöntemini kaydet
            </button>
            <button
              type="button"
              disabled={busy || sub.cancel_at_period_end}
              onClick={() => void onCancel()}
              className="rounded-lg border border-rose-200 px-3 py-2 text-sm text-rose-700 disabled:opacity-50"
            >
              {sub.cancel_at_period_end ? "İptal planlandı" : "Aboneliği iptal et"}
            </button>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Faturalar</h3>
            {invoices.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">Henüz fatura yok.</p>
            ) : (
              <ul className="mt-2 divide-y divide-slate-100 text-sm">
                {invoices.map((inv) => (
                  <li key={inv.id} className="flex items-center justify-between py-2">
                    <span>
                      {inv.number} · {inv.status} · {inv.currency} {inv.total}
                    </span>
                    <button
                      type="button"
                      className="text-slate-700 underline"
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
    </section>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900">{value}</dd>
    </div>
  );
}
