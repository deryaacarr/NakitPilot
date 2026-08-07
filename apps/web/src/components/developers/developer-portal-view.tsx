"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiKeysPanel } from "@/components/api-keys/api-keys-panel";
import { ErrorState } from "@/components/errors/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { SkeletonBlock } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { WebhookDeliveriesPanel } from "@/components/webhooks/webhook-deliveries-panel";
import {
  getDeveloperDocs,
  getDeveloperErrors,
  getDeveloperUsage,
  type PortalDocs,
  type PortalError,
  type UsageStats,
} from "@/lib/developers/api";
import {
  createWebhookEndpoint,
  listWebhookEndpoints,
  testWebhookEndpoint,
  type WebhookEndpoint,
} from "@/lib/webhooks/api";

function unwrapList<T>(data: { results: T[] } | T[]): T[] {
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

function formatDateTime(value: string) {
  try {
    return new Intl.DateTimeFormat("tr-TR", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function UsageChart({ series }: { series: UsageStats["series"] }) {
  const max = Math.max(1, ...series.map((p) => p.total));
  const width = 560;
  const height = 160;
  const pad = 16;
  const barW = (width - pad * 2) / Math.max(series.length, 1);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full" role="img" aria-label="API kullanım grafiği">
      {series.map((point, i) => {
        const h = (point.total / max) * (height - pad * 2);
        const x = pad + i * barW;
        const y = height - pad - h;
        const errH = point.total ? (point.errors / max) * (height - pad * 2) : 0;
        return (
          <g key={point.date}>
            <rect
              x={x + 2}
              y={y}
              width={Math.max(barW - 4, 2)}
              height={Math.max(h, 0)}
              fill="#0f766e"
              opacity={0.85}
              rx={2}
            />
            {errH > 0 ? (
              <rect
                x={x + 2}
                y={height - pad - errH}
                width={Math.max(barW - 4, 2)}
                height={errH}
                fill="#b91c1c"
                opacity={0.9}
                rx={2}
              />
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}

export function DeveloperPortalView() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<PortalDocs | null>(null);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [errors, setErrors] = useState<PortalError[]>([]);
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [busy, setBusy] = useState(false);

  const [epName, setEpName] = useState("");
  const [epUrl, setEpUrl] = useState("");
  const [testEndpointId, setTestEndpointId] = useState("");
  const [testEvent, setTestEvent] = useState("payment.created");
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setForbidden(false);
    const [docsRes, usageRes, errorsRes, epRes] = await Promise.all([
      getDeveloperDocs(),
      getDeveloperUsage(14),
      getDeveloperErrors(25),
      listWebhookEndpoints(),
    ]);
    setLoading(false);

    if (!docsRes.ok) {
      if (docsRes.error.kind === "forbidden") {
        setForbidden(true);
        return;
      }
      setError(docsRes.error.message);
      return;
    }
    setDocs(docsRes.data);
    if (usageRes.ok) setUsage(usageRes.data);
    if (errorsRes.ok) setErrors(errorsRes.data.results);
    if (epRes.ok) {
      const list = unwrapList(epRes.data);
      setEndpoints(list);
      if (!testEndpointId && list[0]) setTestEndpointId(String(list[0].id));
    }
    if (docsRes.data.webhook_events[0] && !testEvent) {
      setTestEvent(docsRes.data.webhook_events[0].value);
    }
  }, [testEndpointId, testEvent]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial load only
  }, []);

  const eventOptions = useMemo(
    () => (docs?.webhook_events ?? []).map((e) => ({ value: e.value, label: `${e.value}` })),
    [docs],
  );

  const endpointOptions = useMemo(
    () => endpoints.map((e) => ({ value: String(e.id), label: `${e.name} (${e.url})` })),
    [endpoints],
  );

  const onCreateEndpoint = async () => {
    if (!epName.trim() || !epUrl.trim()) {
      toast({ title: "Eksik bilgi", description: "İsim ve URL gerekli.", tone: "error" });
      return;
    }
    setBusy(true);
    const result = await createWebhookEndpoint({
      name: epName.trim(),
      url: epUrl.trim(),
      event_types: docs?.webhook_events.map((e) => e.value) ?? [],
    });
    setBusy(false);
    if (!result.ok) {
      toast({ title: "Endpoint oluşturulamadı", description: result.error.message, tone: "error" });
      return;
    }
    setCreatedSecret(result.data.secret ?? null);
    setEpName("");
    setEpUrl("");
    toast({ title: "Webhook endpoint eklendi", tone: "success" });
    await load();
  };

  const onTestSend = async () => {
    if (!testEndpointId) {
      toast({ title: "Endpoint seçin", tone: "error" });
      return;
    }
    setBusy(true);
    const result = await testWebhookEndpoint(testEndpointId, { event_type: testEvent });
    setBusy(false);
    if (!result.ok) {
      toast({ title: "Test gönderilemedi", description: result.error.message, tone: "error" });
      return;
    }
    const delivery = result.data.deliveries[0];
    toast({
      title: "Test webhook gönderildi",
      description: delivery
        ? `Durum: ${delivery.status} · ${delivery.public_id}`
        : undefined,
      tone: "success",
    });
    await load();
  };

  if (loading) {
    return <SkeletonBlock className="h-64 w-full rounded-xl" />;
  }

  if (forbidden) {
    return (
      <ErrorState
        error={{
          kind: "forbidden",
          title: "Yetkiniz yok",
          message: "Geliştirici portalını yalnızca organizasyon yöneticisi görebilir.",
          status: 403,
        }}
      />
    );
  }

  if (error || !docs) {
    return <ErrorState error={error ?? "Yüklenemedi"} onRetry={() => void load()} />;
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-serif text-2xl tracking-tight text-slate-900">Endpoint dokümantasyonu</h2>
        <p className="mt-1 text-sm text-slate-600">
          Auth: <code className="text-xs">{docs.auth.header}</code> · OpenAPI:{" "}
          <a className="text-teal-800 underline" href={docs.openapi_docs_url} target="_blank" rel="noreferrer">
            Swagger UI
          </a>{" "}
          /{" "}
          <a className="text-teal-800 underline" href={docs.openapi_schema_url} target="_blank" rel="noreferrer">
            Schema
          </a>
        </p>
        <ul className="mt-4 space-y-4">
          {docs.endpoints.map((ep) => (
            <li key={`${ep.method}-${ep.path}`} className="rounded-lg border border-slate-100 p-3">
              <p className="text-sm font-semibold text-slate-900">
                <span className="font-mono text-teal-800">{ep.method}</span> {ep.path}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                {ep.summary} · scope <code>{ep.scope}</code>
              </p>
              {ep.headers ? (
                <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-[11px] text-slate-700">
                  {JSON.stringify(ep.headers, null, 2)}
                </pre>
              ) : null}
              {ep.request_example ? (
                <div className="mt-2">
                  <p className="text-xs font-medium text-slate-500">Request</p>
                  <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2 text-[11px] text-slate-700">
                    {JSON.stringify(ep.request_example, null, 2)}
                  </pre>
                </div>
              ) : null}
              <div className="mt-2">
                <p className="text-xs font-medium text-slate-500">Response</p>
                <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2 text-[11px] text-slate-700">
                  {JSON.stringify(ep.response_example, null, 2)}
                </pre>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <ApiKeysPanel />

      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-serif text-2xl tracking-tight text-slate-900">API kullanım</h2>
        {usage ? (
          <>
            <dl className="grid gap-2 sm:grid-cols-3">
              <div className="rounded-lg border border-slate-100 px-3 py-2">
                <dt className="text-xs text-slate-500">Toplam (14 gün)</dt>
                <dd className="text-lg font-semibold text-slate-900">{usage.totals.total}</dd>
              </div>
              <div className="rounded-lg border border-slate-100 px-3 py-2">
                <dt className="text-xs text-slate-500">Başarılı</dt>
                <dd className="text-lg font-semibold text-slate-900">{usage.totals.success}</dd>
              </div>
              <div className="rounded-lg border border-slate-100 px-3 py-2">
                <dt className="text-xs text-slate-500">Hatalı</dt>
                <dd className="text-lg font-semibold text-red-700">{usage.totals.errors}</dd>
              </div>
            </dl>
            <UsageChart series={usage.series} />
            <p className="text-xs text-slate-500">Teal: istek · Kırmızı: hata</p>
          </>
        ) : (
          <p className="text-sm text-slate-500">Kullanım verisi yok.</p>
        )}
      </section>

      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-serif text-2xl tracking-tight text-slate-900">Webhook event listesi</h2>
        <ul className="grid gap-2 sm:grid-cols-2">
          {docs.webhook_events.map((ev) => (
            <li key={ev.value} className="rounded-lg border border-slate-100 px-3 py-2 font-mono text-xs text-slate-800">
              {ev.value}
            </li>
          ))}
        </ul>
        <p className="text-xs text-slate-500">
          İmza header’ları: {docs.webhook_headers.join(", ")}
        </p>
      </section>

      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-serif text-2xl tracking-tight text-slate-900">Webhook test gönderimi</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label="Yeni endpoint adı" value={epName} onChange={(e) => setEpName(e.target.value)} />
          <Input
            label="URL"
            value={epUrl}
            onChange={(e) => setEpUrl(e.target.value)}
            placeholder="https://example.com/hooks"
          />
        </div>
        <Button onClick={() => void onCreateEndpoint()} loading={busy}>
          Endpoint oluştur
        </Button>
        {createdSecret ? (
          <div className="rounded-lg border border-teal-200 bg-teal-50/50 px-3 py-2 text-sm">
            <p className="font-semibold text-teal-900">Signing secret (bir kez)</p>
            <code className="mt-1 block break-all text-xs">{createdSecret}</code>
          </div>
        ) : null}
        <div className="grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2">
          <Select
            label="Endpoint"
            options={endpointOptions}
            value={testEndpointId}
            onChange={(e) => setTestEndpointId(e.target.value)}
            placeholder="Seçin"
            disabled={endpointOptions.length === 0}
          />
          <Select
            label="Event"
            options={eventOptions}
            value={testEvent}
            onChange={(e) => setTestEvent(e.target.value)}
          />
        </div>
        <Button variant="outline" onClick={() => void onTestSend()} loading={busy} disabled={!testEndpointId}>
          Test webhook gönder
        </Button>
      </section>

      <WebhookDeliveriesPanel />

      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-serif text-2xl tracking-tight text-slate-900">Son hata kayıtları</h2>
        {errors.length === 0 ? (
          <p className="text-sm text-slate-500">Kayıt yok.</p>
        ) : (
          <ul className="space-y-2">
            {errors.map((row) => (
              <li key={`${row.source}-${row.id}`} className="rounded-lg border border-slate-100 px-3 py-2">
                <p className="text-sm font-medium text-slate-900">
                  <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase text-slate-600">
                    {row.source}
                  </span>
                  {row.title}
                </p>
                <p className="mt-0.5 text-xs text-slate-600">{row.detail}</p>
                <p className="mt-0.5 text-[11px] text-slate-400">{formatDateTime(row.at)}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
