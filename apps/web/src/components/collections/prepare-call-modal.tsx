"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { fetchPrepareCall, type CallPrepPayload } from "@/lib/collections/api";
import { formatDate, formatMoney } from "@/lib/customers/format";

export function PrepareCallModal({
  taskId,
  customerName,
  onClose,
}: {
  taskId: number;
  customerName: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<CallPrepPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchPrepareCall(taskId).then((result) => {
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
  }, [taskId]);

  return (
    <Modal
      open
      onClose={onClose}
      title="Aramadan önce hazırla"
      description={customerName}
      size="lg"
      footer={
        <div className="flex justify-end">
          <Button type="button" onClick={onClose}>
            Kapat
          </Button>
        </div>
      }
    >
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {!data && !error ? <p className="text-sm text-slate-500">Yükleniyor…</p> : null}
      {data ? (
        <div className="space-y-5 text-sm">
          <section>
            <h3 className="font-semibold text-slate-900">Görüşmede değinilecek noktalar</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-700">
              {data.talking_points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </section>

          <section>
            <h3 className="font-semibold text-slate-900">Açık faturalar</h3>
            {data.open_invoices.length === 0 ? (
              <p className="mt-1 text-slate-500">Açık fatura yok.</p>
            ) : (
              <ul className="mt-2 space-y-1 text-slate-700">
                {data.open_invoices.map((inv) => (
                  <li key={inv.id}>
                    {inv.number} · {formatMoney(inv.remaining_amount)} ·{" "}
                    {inv.overdue_days > 0 ? `${inv.overdue_days} gün gecikme` : "vadesi gelmemiş"}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="font-semibold text-slate-900">Son ödeme sözü</h3>
            {data.last_payment_promise ? (
              <p className="mt-1 text-slate-700">
                {formatMoney(data.last_payment_promise.amount)} ·{" "}
                {formatDate(data.last_payment_promise.promised_date)} (
                {data.last_payment_promise.status})
              </p>
            ) : (
              <p className="mt-1 text-slate-500">Kayıt yok.</p>
            )}
          </section>

          <section>
            <h3 className="font-semibold text-slate-900">Son itiraz</h3>
            {data.last_objection ? (
              <p className="mt-1 text-slate-700">{data.last_objection.notes || "—"}</p>
            ) : (
              <p className="mt-1 text-slate-500">Kayıt yok.</p>
            )}
          </section>

          <section>
            <h3 className="font-semibold text-slate-900">Önceki görüşme notları</h3>
            {data.previous_call_notes.length === 0 ? (
              <p className="mt-1 text-slate-500">Kayıt yok.</p>
            ) : (
              <ul className="mt-2 space-y-2 text-slate-700">
                {data.previous_call_notes.map((n) => (
                  <li key={n.id} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                    <p className="text-xs text-slate-400">
                      {formatDate(n.occurred_at.slice(0, 10))}
                    </p>
                    <p>{n.notes || n.summary}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="font-semibold text-slate-900">Ödeme planı önerileri</h3>
            <p className="mt-1 text-xs text-amber-800">
              Bağlayıcı değildir — uygulamadan önce müşteri detayından onaylayın.
            </p>
            {data.payment_plan_suggestions?.options?.length ? (
              <ul className="mt-2 space-y-2 text-slate-700">
                {data.payment_plan_suggestions.options.map((opt) => (
                  <li
                    key={opt.id}
                    className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"
                  >
                    <p className="font-medium text-slate-900">{opt.title}</p>
                    <p className="text-sm">{opt.summary}</p>
                  </li>
                ))}
              </ul>
            ) : data.suggested_payment_plan ? (
              <p className="mt-1 text-slate-700">{data.suggested_payment_plan.label}</p>
            ) : (
              <p className="mt-1 text-slate-500">Açık bakiye yok.</p>
            )}
          </section>
        </div>
      ) : null}
    </Modal>
  );
}
