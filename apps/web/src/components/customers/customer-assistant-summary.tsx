"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchCustomerSummary, type CustomerSummaryPayload } from "@/lib/risk/api";

export function CustomerAssistantSummary({ customerId }: { customerId: number }) {
  const [data, setData] = useState<CustomerSummaryPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSources, setShowSources] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void fetchCustomerSummary(customerId).then((result) => {
      if (cancelled) return;
      if (!result.ok) {
        setError(result.error.message);
        setData(null);
        return;
      }
      setError(null);
      setData(result.data);
    });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  if (error) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Müşteri özeti</h2>
        <p className="mt-2 text-sm text-slate-500">{error}</p>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Müşteri özeti</h2>
        <p className="mt-2 text-sm text-slate-500">Yükleniyor…</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-900">Müşteri özeti</h2>
        <button
          type="button"
          onClick={() => setShowSources((v) => !v)}
          className="text-brand text-xs font-semibold hover:underline"
        >
          {showSources ? "Kaynakları gizle" : "Kaynak kayıtlar"}
        </button>
      </div>
      <ul className="mt-3 space-y-2 text-sm leading-relaxed text-slate-800">
        {data.paragraphs.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
      {showSources ? (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <p className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Kaynaklar (veritabanı)
          </p>
          <ul className="mt-2 space-y-1.5 text-sm text-slate-600">
            {data.sources.map((s) => (
              <li key={`${s.type}-${s.id}-${s.field}`}>
                {s.url_hint ? (
                  <Link href={s.url_hint} className="text-brand hover:underline">
                    {s.label}
                  </Link>
                ) : (
                  <span>{s.label}</span>
                )}
                <span className="text-slate-400"> · {s.field}=</span>
                <span>{String(s.value ?? "—")}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
