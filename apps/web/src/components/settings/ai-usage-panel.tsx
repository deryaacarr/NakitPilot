"use client";

import { useEffect, useState } from "react";

import { fetchAIUsageSummary, type AIUsageSummary } from "@/lib/ai-usage/api";

export function AIUsagePanel() {
  const [data, setData] = useState<AIUsageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchAIUsageSummary().then((result) => {
      if (cancelled) return;
      if (!result.ok) {
        setError(result.error.message);
        return;
      }
      setData(result.data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">AI maliyet kontrolü</h2>
      <p className="mt-1 text-xs text-slate-500">
        Paket kullanımı, günlük kullanıcı limiti, organizasyon bütçesi, içerik kısaltma ve önbellek.
      </p>
      {error ? <p className="mt-3 text-sm text-slate-500">{error}</p> : null}
      {!data && !error ? <p className="mt-3 text-sm text-slate-500">Yükleniyor…</p> : null}
      {data ? (
        <dl className="mt-4 grid gap-3 sm:grid-cols-2 text-sm">
          <Item label="Paket" value={data.package} />
          <Item
            label="Aylık token"
            value={`${data.usage.month.total_tokens} / ${data.limits.package_monthly_tokens}`}
          />
          <Item
            label="Günlük kullanıcı token"
            value={
              data.usage.today_user
                ? `${data.usage.today_user.total_tokens} / ${data.limits.daily_user_tokens}`
                : `— / ${data.limits.daily_user_tokens}`
            }
          />
          <Item
            label="Org. bütçe (ay)"
            value={`${data.usage.month.estimated_cost} / ${data.limits.org_budget_monthly}`}
          />
          <Item label="Maks. içerik" value={`${data.limits.max_input_chars} karakter`} />
          <Item label="Önbellek TTL" value={`${data.limits.cache_ttl_seconds} sn`} />
        </dl>
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
