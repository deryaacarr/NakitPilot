"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors/error-state";
import { Button } from "@/components/ui/button";
import { SkeletonBlock } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { listWebhookDeliveries, resendWebhookDelivery } from "@/lib/webhooks/api";
import type { WebhookDelivery } from "@/lib/webhooks/types";

function formatDateTime(value: string | null) {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("tr-TR", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function unwrap(data: { results: WebhookDelivery[] } | WebhookDelivery[]): WebhookDelivery[] {
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

const STATUS_LABEL: Record<string, string> = {
  failed: "Başarısız",
  exhausted: "Tükendi",
  pending: "Bekliyor",
  in_progress: "Gönderiliyor",
  succeeded: "Başarılı",
};

export function WebhookDeliveriesPanel() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [rows, setRows] = useState<WebhookDelivery[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    setForbidden(false);
    const result = await listWebhookDeliveries("failed");
    setLoading(false);
    if (!result.ok) {
      if (result.error.kind === "forbidden") {
        setForbidden(true);
        return;
      }
      setLoadError(result.error.message);
      return;
    }
    setRows(unwrap(result.data));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onResend = async (row: WebhookDelivery) => {
    setBusyId(row.id);
    const result = await resendWebhookDelivery(row.id);
    setBusyId(null);
    if (!result.ok) {
      toast({ title: "Yeniden gönderilemedi", description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "Yeniden gönderim kuyruğa alındı", tone: "success" });
    await load();
  };

  if (loading) {
    return <SkeletonBlock className="h-40 w-full rounded-xl" />;
  }

  if (forbidden) {
    return (
      <ErrorState
        error={{
          kind: "forbidden",
          title: "Yetkiniz yok",
          message: "Webhook teslimatlarını yalnızca yönetici görebilir.",
          status: 403,
        }}
      />
    );
  }

  if (loadError) {
    return <ErrorState error={loadError} onRetry={() => void load()} />;
  }

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-2xl tracking-tight text-slate-900">
            Başarısız webhook teslimatları
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Retry planı: 1dk → 5dk → 15dk → 1sa → 6sa → 24sa. Aynı teslimat kimliği korunur.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          Yenile
        </Button>
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">Başarısız teslimat yok.</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li key={row.id} className="rounded-lg border border-slate-100 px-3 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    {row.event_type}{" "}
                    <span className="font-normal text-slate-500">
                      · {STATUS_LABEL[row.status] ?? row.status}
                    </span>
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {row.endpoint_name} · {row.endpoint_url}
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-slate-500">
                    delivery: {row.public_id}
                  </p>
                  <p className="mt-1 text-xs text-slate-600">
                    Deneme {row.attempt_count}/{row.max_attempts}
                    {row.next_attempt_at
                      ? ` · sonraki: ${formatDateTime(row.next_attempt_at)}`
                      : ""}
                  </p>
                  {row.last_error ? (
                    <p className="mt-1 text-xs text-red-700">{row.last_error}</p>
                  ) : null}
                  {row.attempts?.length ? (
                    <p className="mt-1 text-xs text-slate-500">
                      Son deneme: #
                      {row.attempts[row.attempts.length - 1]?.attempt_number} · HTTP{" "}
                      {row.attempts[row.attempts.length - 1]?.response_status ?? "—"}
                    </p>
                  ) : null}
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  loading={busyId === row.id}
                  onClick={() => void onResend(row)}
                >
                  Manuel tekrar gönder
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
