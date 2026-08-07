"use client";

import { useEffect, useState } from "react";

import { fetchCustomerRiskExplanation } from "@/lib/customers/api";
import type { RiskExplanation } from "@/lib/customers/types";
import { cn } from "@/lib/cn";

export function CustomerRiskExplanation({ customerId }: { customerId: number }) {
  const [data, setData] = useState<RiskExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchCustomerRiskExplanation(customerId).then((result) => {
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
        <h2 className="text-sm font-semibold text-slate-900">Risk açıklaması</h2>
        <p className="mt-2 text-sm text-slate-500">{error}</p>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Risk açıklaması</h2>
        <p className="mt-2 text-sm text-slate-500">Yükleniyor…</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">Risk açıklaması</h2>
      <p className="mt-2 font-serif text-xl tracking-tight text-slate-900">{data.headline}</p>
      <p className="mt-4 text-xs font-semibold tracking-wide text-slate-500 uppercase">
        Başlıca nedenler
      </p>
      {data.reasons.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">Belirgin risk faktörü yok.</p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {data.reasons.map((reason) => (
            <li
              key={`${reason.code}-${reason.text}`}
              className={cn(
                "flex gap-2 text-sm",
                reason.sign === "+" ? "text-rose-700" : "text-emerald-700",
              )}
            >
              <span className="w-4 shrink-0 font-semibold">{reason.sign}</span>
              <span>{reason.text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
