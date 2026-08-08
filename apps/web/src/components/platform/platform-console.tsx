"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { setOrganizationId } from "@/lib/api/organization";
import {
  getAccessToken,
  getRefreshToken,
  saveTokens,
  wasRemembered,
} from "@/lib/auth/storage";
import type { AppError } from "@/lib/errors";
import {
  createMaintenanceWindow,
  createSupportTicket,
  endImpersonation,
  fetchFeatureFlags,
  fetchPlatformOverview,
  startImpersonation,
  upsertFeatureFlag,
} from "@/lib/platform/api";
import type { FeatureFlag, PlatformOverview } from "@/lib/platform/types";

const STAFF_TOKEN_BACKUP = "nakitpilot.staff_token_backup";

export function PlatformConsole() {
  const { toast } = useToast();
  const [data, setData] = useState<PlatformOverview | null>(null);
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);

  const [impUserId, setImpUserId] = useState("");
  const [impOrgId, setImpOrgId] = useState("");
  const [impReason, setImpReason] = useState("");
  const [maintOrgId, setMaintOrgId] = useState("");
  const [maintMessage, setMaintMessage] = useState("Planlı bakım");
  const [ticketSubject, setTicketSubject] = useState("");
  const [ticketOrgId, setTicketOrgId] = useState("");

  const load = useCallback(async () => {
    const [overview, flagRes] = await Promise.all([
      fetchPlatformOverview(false),
      fetchFeatureFlags(),
    ]);
    setLoading(false);
    if (!overview.ok) {
      setError(overview.error);
      return;
    }
    setError(null);
    setData(overview.data);
    if (flagRes.ok) setFlags(flagRes.data.results || []);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingSkeleton lines={12} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!data) return null;

  return (
    <div className="space-y-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Platform
        </p>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Super admin paneli</h1>
        <p className="mt-1 text-sm text-slate-600">{data.privacy.note}</p>
      </header>

      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Organizasyon" value={String(data.totals.organizations)} />
        <Metric label="Aktif kullanıcı" value={String(data.totals.active_users)} />
        <Metric label="Üyelik" value={String(data.totals.active_memberships)} />
        <Metric label="AI maliyet" value={`₺${data.ai_cost.estimated_cost_total}`} />
        <Metric
          label="Depolama"
          value={`${(data.storage.file_storage_bytes / (1024 * 1024)).toFixed(1)} MB`}
        />
        <Metric label="AI olay" value={String(data.ai_cost.events)} />
      </dl>

      <section className="grid gap-4 lg:grid-cols-2">
        <Panel title="Organizasyonlar">
          <ul className="max-h-64 space-y-2 overflow-y-auto text-sm">
            {data.organizations.map((o) => (
              <li key={o.id} className="flex justify-between border-b border-slate-100 py-1">
                <span>
                  #{o.id} {o.name}
                </span>
                <span className="tabular-nums text-slate-500">{o.user_count} kullanıcı</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Planlar / abonelikler">
          <ul className="space-y-2 text-sm">
            {data.plans.map((p) => (
              <li key={p.id} className="flex justify-between">
                <span>
                  {p.code} — {p.name}
                </span>
                <span>{p.sub_count}</span>
              </li>
            ))}
          </ul>
          <ul className="mt-3 max-h-40 space-y-1 overflow-y-auto text-xs text-slate-600">
            {data.subscriptions.slice(0, 12).map((s) => (
              <li key={s.id}>
                {s.organization_name}: {s.plan_code} ({s.status})
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Entegrasyon durumları">
          <ul className="space-y-1 text-sm">
            {data.integrations.by_status.map((row) => (
              <li key={row.status} className="flex justify-between">
                <span>{row.status}</span>
                <span>{row.count}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Son hatalar">
          <ul className="max-h-64 space-y-2 overflow-y-auto text-xs">
            {data.last_errors.length === 0 ? (
              <li className="text-slate-500">Kayıt yok</li>
            ) : (
              data.last_errors.map((e) => (
                <li key={`${e.source}-${e.id}`} className="rounded bg-slate-50 p-2">
                  <Badge tone="warning">{e.source}</Badge>
                  <p className="mt-1">{e.message}</p>
                </li>
              ))
            )}
          </ul>
        </Panel>
        <Panel title="Destek talepleri">
          <ul className="mb-3 max-h-40 space-y-1 overflow-y-auto text-sm">
            {data.support_tickets.map((t) => (
              <li key={t.id}>
                #{t.id} {t.subject} — {t.organization_name}{" "}
                <Badge>{t.status}</Badge>
              </li>
            ))}
          </ul>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={ticketOrgId}
              onChange={(e) => setTicketOrgId(e.target.value)}
              placeholder="Org ID"
              className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
            />
            <input
              value={ticketSubject}
              onChange={(e) => setTicketSubject(e.target.value)}
              placeholder="Konu"
              className="flex-1 rounded-lg border border-slate-200 px-2 py-1 text-sm"
            />
            <Button
              size="sm"
              onClick={async () => {
                const result = await createSupportTicket({
                  organization_id: Number(ticketOrgId),
                  subject: ticketSubject,
                });
                if (!result.ok) {
                  toast({ title: "Oluşturulamadı", tone: "error" });
                  return;
                }
                toast({ title: "Talep açıldı", tone: "success" });
                void load();
              }}
            >
              Ekle
            </Button>
          </div>
        </Panel>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-900">Feature flags</h2>
        <ul className="mt-3 space-y-2">
          {flags.map((flag) => (
            <li
              key={flag.key}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm"
            >
              <div>
                <p className="font-medium">{flag.key}</p>
                <p className="text-xs text-slate-500">
                  %{flag.rollout_percentage} · plan:{(flag.plan_codes || []).join(",") || "*"} ·
                  env:{(flag.environments || []).join(",") || "*"}
                </p>
              </div>
              <Button
                size="sm"
                variant={flag.enabled ? "secondary" : "primary"}
                onClick={async () => {
                  const result = await upsertFeatureFlag({
                    key: flag.key,
                    enabled: !flag.enabled,
                    rollout_percentage: flag.rollout_percentage,
                    organization_ids: flag.organization_ids,
                    plan_codes: flag.plan_codes,
                    environments: flag.environments,
                    description: flag.description,
                  });
                  if (!result.ok) {
                    toast({ title: "Flag güncellenemedi", tone: "error" });
                    return;
                  }
                  void load();
                }}
              >
                {flag.enabled ? "Kapat" : "Aç"}
              </Button>
            </li>
          ))}
        </ul>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Panel title="Impersonation (destek)">
          <p className="mb-3 text-xs text-slate-500">
            Gerekçe zorunlu, süre max 60 dk, finansal yazmalar engellenir, audit log yazılır.
          </p>
          <div className="space-y-2">
            <input
              value={impUserId}
              onChange={(e) => setImpUserId(e.target.value)}
              placeholder="Hedef kullanıcı ID"
              className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm"
            />
            <input
              value={impOrgId}
              onChange={(e) => setImpOrgId(e.target.value)}
              placeholder="Organizasyon ID"
              className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm"
            />
            <textarea
              value={impReason}
              onChange={(e) => setImpReason(e.target.value)}
              placeholder="Gerekçe (zorunlu)"
              className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm"
              rows={2}
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={async () => {
                  const access = getAccessToken();
                  const refresh = getRefreshToken();
                  if (access && refresh) {
                    sessionStorage.setItem(
                      STAFF_TOKEN_BACKUP,
                      JSON.stringify({ access, refresh, remember: wasRemembered() }),
                    );
                  }
                  const result = await startImpersonation({
                    user_id: Number(impUserId),
                    organization_id: Number(impOrgId),
                    reason: impReason,
                    duration_minutes: 30,
                  });
                  if (!result.ok) {
                    toast({
                      title: "Impersonation başarısız",
                      description: result.error.message,
                      tone: "error",
                    });
                    return;
                  }
                  saveTokens(result.data.access, result.data.refresh, wasRemembered());
                  setOrganizationId(result.data.organization_id);
                  toast({ title: "Destek oturumu başladı", tone: "warning" });
                  window.location.href = "/collections/field";
                }}
              >
                Geçiş yap
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={async () => {
                  await endImpersonation();
                  const backup = sessionStorage.getItem(STAFF_TOKEN_BACKUP);
                  if (backup) {
                    const tokens = JSON.parse(backup) as {
                      access: string;
                      refresh: string;
                      remember?: boolean;
                    };
                    saveTokens(tokens.access, tokens.refresh, Boolean(tokens.remember));
                    sessionStorage.removeItem(STAFF_TOKEN_BACKUP);
                  }
                  toast({ title: "Impersonation sonlandı", tone: "success" });
                  window.location.href = "/dashboard/platform";
                }}
              >
                Bitir / staff’a dön
              </Button>
            </div>
          </div>
        </Panel>

        <Panel title="Bakım modu">
          <div className="space-y-2">
            <input
              value={maintOrgId}
              onChange={(e) => setMaintOrgId(e.target.value)}
              placeholder="Org ID (boş = global)"
              className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm"
            />
            <input
              value={maintMessage}
              onChange={(e) => setMaintMessage(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm"
            />
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={async () => {
                  const result = await createMaintenanceWindow({
                    scope: maintOrgId ? "ORGANIZATION" : "GLOBAL",
                    mode: "READ_ONLY",
                    organization_id: maintOrgId ? Number(maintOrgId) : null,
                    message: maintMessage,
                  });
                  if (!result.ok) {
                    toast({ title: "Oluşturulamadı", tone: "error" });
                    return;
                  }
                  toast({ title: "Salt okunur bakım açıldı", tone: "warning" });
                }}
              >
                Salt okunur
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={async () => {
                  const result = await createMaintenanceWindow({
                    scope: maintOrgId ? "ORGANIZATION" : "GLOBAL",
                    mode: "FULL",
                    organization_id: maintOrgId ? Number(maintOrgId) : null,
                    message: maintMessage,
                  });
                  if (!result.ok) {
                    toast({ title: "Oluşturulamadı", tone: "error" });
                    return;
                  }
                  toast({ title: "Tam bakım açıldı", tone: "error" });
                }}
              >
                Tam bakım
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={async () => {
                  const result = await createMaintenanceWindow({
                    scope: "MODULE",
                    mode: "READ_ONLY",
                    module: "legal",
                    organization_id: maintOrgId ? Number(maintOrgId) : null,
                    message: maintMessage || "Hukuki modül bakımda",
                  });
                  if (!result.ok) {
                    toast({ title: "Oluşturulamadı", tone: "error" });
                    return;
                  }
                  toast({ title: "Modül bakımı (legal)", tone: "warning" });
                }}
              >
                Legal modül
              </Button>
            </div>
          </div>
        </Panel>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{value}</dd>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}
