"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import {
  acceptPaymentPlan,
  fetchPaymentPlanSuggestions,
  type PaymentPlanOption,
  type PaymentPlanOptionId,
  type PaymentPlanSuggestions,
} from "@/lib/collections/api";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { cn } from "@/lib/cn";

export function CustomerPaymentPlanSuggestions({ customerId }: { customerId: number }) {
  const { toast } = useToast();
  const [data, setData] = useState<PaymentPlanSuggestions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PaymentPlanOptionId | null>(null);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    const result = await fetchPaymentPlanSuggestions(customerId);
    if (!result.ok) {
      setError(result.error.message);
      setData(null);
      return;
    }
    setError(null);
    setData(result.data);
    setSelected(result.data.options[0]?.id ?? null);
  }, [customerId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onAccept = async () => {
    if (!selected || !data) return;
    setConfirming(true);
    const result = await acceptPaymentPlan(customerId, {
      option_id: selected,
      confirmed: true,
    });
    setConfirming(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    toast({
      title: "Plan onaylandı",
      description: `${result.data.option_title} · ${result.data.promise_ids.length} ödeme sözü oluşturuldu`,
      tone: "success",
    });
    void load();
  };

  if (error) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Ödeme planı önerisi</h2>
        <p className="mt-2 text-sm text-slate-500">{error}</p>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Ödeme planı önerisi</h2>
        <p className="mt-2 text-sm text-slate-500">Yükleniyor…</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Ödeme planı önerisi</h2>
          <p className="mt-1 text-xs text-slate-500">
            Açık bakiye {formatMoney(data.open_balance)} · bağlayıcı değildir, onay gerekir
          </p>
        </div>
      </div>

      <p className="mt-3 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-900">
        {data.disclaimer}
      </p>

      {data.options.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">Açık bakiye yok — öneri üretilemedi.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {data.options.map((opt) => (
            <OptionCard
              key={opt.id}
              option={opt}
              selected={selected === opt.id}
              onSelect={() => setSelected(opt.id)}
            />
          ))}
        </ul>
      )}

      <div className="mt-4 flex justify-end">
        <Button
          onClick={() => void onAccept()}
          loading={confirming}
          disabled={!selected || data.options.length === 0}
        >
          Seçili planı onayla
        </Button>
      </div>
    </section>
  );
}

function OptionCard({
  option,
  selected,
  onSelect,
}: {
  option: PaymentPlanOption;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className={cn(
          "w-full rounded-lg border px-3 py-3 text-left transition",
          selected
            ? "border-brand/40 bg-brand/5"
            : "border-slate-200 bg-slate-50 hover:border-slate-300",
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-slate-900">{option.title}</span>
          <span className="text-xs text-slate-500">{formatMoney(option.total_amount)}</span>
        </div>
        <p className="mt-1 text-sm text-slate-700">{option.summary}</p>
        <ul className="mt-2 space-y-0.5 text-xs text-slate-600">
          {option.steps.map((step) => (
            <li key={`${step.due_date}-${step.amount}-${step.label}`}>
              {step.label} · {formatDate(step.due_date)}
            </li>
          ))}
        </ul>
      </button>
    </li>
  );
}
