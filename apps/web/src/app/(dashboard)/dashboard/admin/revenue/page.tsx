"use client";

import { useEffect, useState } from "react";

import { fetchAdminRevenue, type RevenueMetrics } from "@/lib/billing/api";

export default function AdminRevenuePage() {
  const [data, setData] = useState<RevenueMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchAdminRevenue().then((result) => {
      if (!result.ok) {
        setError(result.error.message);
        return;
      }
      setData(result.data);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Gelir paneli</h1>
        <p className="mt-1 text-sm text-slate-600">
          MRR, ARR, deneme dönüşümü, churn ve paket dağılımı (yalnızca admin).
        </p>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {!data && !error ? <p className="text-sm text-slate-500">Yükleniyor…</p> : null}
      {data ? (
        <>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="MRR" value={`₺${data.mrr}`} />
            <Metric label="ARR" value={`₺${data.arr}`} />
            <Metric label="Aktif abonelik" value={String(data.active_subscriptions)} />
            <Metric label="Deneme kullanıcıları" value={String(data.trial_users)} />
            <Metric label="Dönüşüm oranı" value={`%${data.conversion_rate}`} />
            <Metric label="Churn" value={`%${data.churn}`} />
            <Metric label="ARPU" value={`₺${data.arpu}`} />
            <Metric label="Başarısız ödeme" value={String(data.failed_payments)} />
          </dl>
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">Paket dağılımı</h2>
            <ul className="mt-3 space-y-2 text-sm">
              {Object.entries(data.plan_distribution).map(([code, count]) => (
                <li key={code} className="flex justify-between border-b border-slate-100 py-1">
                  <span>{code}</span>
                  <span className="tabular-nums">{count}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-slate-500">Güncelleme: {data.as_of}</p>
          </section>
        </>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{value}</dd>
    </div>
  );
}
