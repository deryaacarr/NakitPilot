"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ErrorState } from "@/components/errors/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SkeletonBlock } from "@/components/ui/loading-skeleton";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  createConnection,
  deleteConnection,
  getMonitoring,
  listCompanies,
  listConflicts,
  listConnections,
  putCredentials,
  resolveConflict,
  selectCompany,
  startSync,
  testConnection,
  updateSyncSettings,
} from "@/lib/integrations/api";
import type {
  CompanyOption,
  IntegrationConnection,
  IntegrationMonitoring,
  SyncConflict,
  SyncConflictResolution,
  SyncFrequency,
} from "@/lib/integrations/types";
import { cn } from "@/lib/cn";

type WizardStep = "credentials" | "companies" | "settings" | "done";

const FREQUENCY_OPTIONS = [
  { value: "manual", label: "Manuel" },
  { value: "hourly", label: "Saatlik" },
  { value: "daily", label: "Günlük" },
];

const STATUS_LABEL: Record<string, string> = {
  draft: "Taslak",
  connected: "Bağlı",
  error: "Hata",
  disabled: "Kapalı",
};

const CONFLICT_TYPE_LABEL: Record<string, string> = {
  duplicate_manual_api: "Manuel + API çakışması",
  local_edited: "Yerel değişiklik",
  payment_amount_changed: "Ödeme tutarı değişti",
  customer_merged_or_deleted: "Müşteri birleşti / silindi",
};

const RESOLUTION_ACTIONS: { value: SyncConflictResolution; label: string }[] = [
  { value: "use_source", label: "Kaynak veriyi kullan" },
  { value: "keep_local", label: "Yerel veriyi koru" },
  { value: "merge", label: "Kayıtları birleştir" },
  { value: "skip_field_forever", label: "Bu alanı gelecekte senkronize etme" },
];

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

function formatMs(value: number | null | undefined) {
  if (value == null) return "—";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(1)} s`;
}

function unwrapConnections(
  data: { results: IntegrationConnection[] } | IntegrationConnection[],
): IntegrationConnection[] {
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

export function KolayBiConnectionPanel() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [connection, setConnection] = useState<IntegrationConnection | null>(null);
  const [step, setStep] = useState<WizardStep>("credentials");
  const [busy, setBusy] = useState(false);

  const [apiKey, setApiKey] = useState("");
  const [channelId, setChannelId] = useState("");
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [syncFrequency, setSyncFrequency] = useState<SyncFrequency>("daily");
  const [monitoring, setMonitoring] = useState<IntegrationMonitoring | null>(null);
  const [conflicts, setConflicts] = useState<SyncConflict[]>([]);
  const [skipFieldByConflict, setSkipFieldByConflict] = useState<Record<number, string>>({});

  const isConfigured = Boolean(connection?.external_company_id && connection.has_credentials);

  const loadOps = useCallback(async (connectionId: number) => {
    const [mon, conf] = await Promise.all([
      getMonitoring(connectionId),
      listConflicts(connectionId, "open"),
    ]);
    if (mon.ok) setMonitoring(mon.data);
    if (conf.ok) setConflicts(conf.data);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    setForbidden(false);
    const result = await listConnections();
    setLoading(false);
    if (!result.ok) {
      if (result.error.kind === "forbidden") {
        setForbidden(true);
        return;
      }
      setLoadError(result.error.message);
      return;
    }
    const rows = unwrapConnections(result.data).filter((c) => c.provider === "kolaybi");
    const current = rows[0] ?? null;
    setConnection(current);
    if (current?.external_company_id && current.has_credentials) {
      setStep("done");
      setSelectedCompanyId(current.external_company_id);
      setSyncFrequency(current.sync_frequency);
      void loadOps(current.id);
    } else if (current?.has_credentials) {
      setStep("companies");
      setMonitoring(null);
      setConflicts([]);
    } else {
      setStep("credentials");
      setMonitoring(null);
      setConflicts([]);
    }
  }, [loadOps]);

  useEffect(() => {
    void load();
  }, [load]);

  const companyOptions = useMemo(
    () =>
      companies.map((c) => ({
        value: c.external_id,
        label: c.tax_number ? `${c.name} (${c.tax_number})` : c.name,
      })),
    [companies],
  );

  const ensureConnection = async () => {
    if (connection) return connection;
    const created = await createConnection({
      provider: "kolaybi",
      external_company_id: "",
      external_company_name: "",
    });
    if (!created.ok) {
      toast({ title: "Bağlantı oluşturulamadı", description: created.error.message, tone: "error" });
      return null;
    }
    setConnection(created.data);
    return created.data;
  };

  const onSaveAndTest = async () => {
    if (!apiKey.trim() || !channelId.trim()) {
      toast({
        title: "Eksik bilgi",
        description: "API anahtarı ve Channel ID gerekli.",
        tone: "error",
      });
      return;
    }
    setBusy(true);
    const conn = await ensureConnection();
    if (!conn) {
      setBusy(false);
      return;
    }
    const creds = await putCredentials(conn.id, {
      api_key: apiKey.trim(),
      channel_id: channelId.trim(),
    });
    if (!creds.ok) {
      setBusy(false);
      toast({ title: "Kimlik bilgisi kaydedilemedi", description: creds.error.message, tone: "error" });
      return;
    }
    const tested = await testConnection(conn.id);
    setBusy(false);
    if (!tested.ok) {
      toast({ title: "Bağlantı testi başarısız", description: tested.error.message, tone: "error" });
      if (tested.error.raw && typeof tested.error.raw === "object" && "connection" in tested.error.raw) {
        setConnection((tested.error.raw as { connection: IntegrationConnection }).connection);
      }
      await load();
      return;
    }
    setConnection(tested.data.connection);
    setApiKey("");
    toast({ title: "Bağlantı doğrulandı", tone: "success" });

    setBusy(true);
    const companyList = await listCompanies(conn.id);
    setBusy(false);
    if (!companyList.ok) {
      toast({ title: "Şirketler alınamadı", description: companyList.error.message, tone: "error" });
      return;
    }
    setCompanies(companyList.data);
    setSelectedCompanyId(companyList.data[0]?.external_id ?? "");
    setStep("companies");
  };

  const onSelectCompany = async () => {
    if (!connection || !selectedCompanyId) return;
    const selected = companies.find((c) => c.external_id === selectedCompanyId);
    setBusy(true);
    const result = await selectCompany(connection.id, {
      external_company_id: selectedCompanyId,
      external_company_name: selected?.name,
    });
    setBusy(false);
    if (!result.ok) {
      toast({ title: "Şirket seçilemedi", description: result.error.message, tone: "error" });
      return;
    }
    setConnection(result.data);
    setStep("settings");
    toast({ title: "Şirket seçildi", description: result.data.external_company_name, tone: "success" });
  };

  const onSaveSettingsAndSync = async () => {
    if (!connection) return;
    setBusy(true);
    const settings = await updateSyncSettings(connection.id, { sync_frequency: syncFrequency });
    if (!settings.ok) {
      setBusy(false);
      toast({ title: "Ayarlar kaydedilemedi", description: settings.error.message, tone: "error" });
      return;
    }
    const sync = await startSync(connection.id, "initial");
    setBusy(false);
    if (!sync.ok) {
      toast({ title: "Eşitleme başlatılamadı", description: sync.error.message, tone: "error" });
      await load();
      return;
    }
    setConnection(sync.data.connection);
    setStep("done");
    await loadOps(connection.id);
    toast({ title: "İlk eşitleme tamamlandı", tone: "success" });
  };

  const onManualSync = async () => {
    if (!connection) return;
    setBusy(true);
    const sync = await startSync(connection.id, "manual");
    setBusy(false);
    if (!sync.ok) {
      toast({ title: "Manuel eşitleme başarısız", description: sync.error.message, tone: "error" });
      await load();
      return;
    }
    setConnection(sync.data.connection);
    await loadOps(connection.id);
    toast({ title: "Manuel eşitleme tamamlandı", tone: "success" });
  };

  const onChangeFrequency = async (value: SyncFrequency) => {
    if (!connection) return;
    setSyncFrequency(value);
    setBusy(true);
    const result = await updateSyncSettings(connection.id, { sync_frequency: value });
    setBusy(false);
    if (!result.ok) {
      toast({ title: "Sıklık güncellenemedi", description: result.error.message, tone: "error" });
      return;
    }
    setConnection(result.data);
    toast({ title: "Senkronizasyon sıklığı güncellendi", tone: "success" });
  };

  const onResolve = async (conflict: SyncConflict, resolution: SyncConflictResolution) => {
    if (!connection) return;
    const field = skipFieldByConflict[conflict.id]?.trim();
    if (resolution === "skip_field_forever" && !field) {
      toast({
        title: "Alan gerekli",
        description: "Senkron dışı bırakılacak alan adını yazın (ör. description).",
        tone: "error",
      });
      return;
    }
    setBusy(true);
    const result = await resolveConflict(connection.id, conflict.id, {
      resolution,
      ...(field ? { field } : {}),
    });
    setBusy(false);
    if (!result.ok) {
      toast({ title: "Çakışma çözülemedi", description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "Çakışma çözüldü", tone: "success" });
    await loadOps(connection.id);
  };

  const onDisconnect = async () => {
    if (!connection) return;
    if (!window.confirm("KolayBi bağlantısı kaldırılsın mı?")) return;
    setBusy(true);
    const result = await deleteConnection(connection.id);
    setBusy(false);
    if (!result.ok) {
      toast({ title: "Bağlantı silinemedi", description: result.error.message, tone: "error" });
      return;
    }
    setConnection(null);
    setCompanies([]);
    setMonitoring(null);
    setConflicts([]);
    setStep("credentials");
    toast({ title: "Bağlantı kaldırıldı", tone: "success" });
  };

  const onReconnect = () => {
    setStep("credentials");
    setApiKey("");
    setChannelId("");
  };

  if (loading) {
    return <SkeletonBlock className="h-48 w-full rounded-xl" />;
  }

  if (forbidden) {
    return (
      <ErrorState
        error={{
          kind: "forbidden",
          title: "Yetkiniz yok",
          message: "KolayBi entegrasyonunu yalnızca organizasyon sahibi veya yöneticisi yönetebilir.",
          status: 403,
        }}
      />
    );
  }

  if (loadError) {
    return (
      <ErrorState
        error={loadError}
        onRetry={() => void load()}
      />
    );
  }

  const metrics = monitoring?.metrics;

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-2xl tracking-tight text-slate-900">KolayBi bağlantısı</h2>
          <p className="mt-1 text-sm text-slate-600">
            API anahtarı ile bağlanın, şirketinizi seçin ve eşitlemeyi başlatın.
          </p>
        </div>
        {connection ? (
          <span
            className={cn(
              "rounded-full px-3 py-1 text-xs font-semibold",
              connection.status === "connected" && "bg-teal-50 text-teal-800",
              connection.status === "error" && "bg-red-50 text-red-700",
              connection.status === "draft" && "bg-slate-100 text-slate-700",
              connection.status === "disabled" && "bg-slate-100 text-slate-500",
            )}
          >
            {STATUS_LABEL[connection.status] ?? connection.status}
          </span>
        ) : null}
      </div>

      {isConfigured && step === "done" && connection ? (
        <div className="space-y-6">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
              <dt className="text-xs font-medium text-slate-500">Bağlantı durumu</dt>
              <dd className="mt-0.5 text-sm font-semibold text-slate-900">
                {STATUS_LABEL[connection.status] ?? connection.status}
              </dd>
            </div>
            <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
              <dt className="text-xs font-medium text-slate-500">Bağlı şirket</dt>
              <dd className="mt-0.5 text-sm font-semibold text-slate-900">
                {connection.external_company_name || connection.external_company_id || "—"}
              </dd>
            </div>
            <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
              <dt className="text-xs font-medium text-slate-500">Son başarılı senkronizasyon</dt>
              <dd className="mt-0.5 text-sm font-semibold text-slate-900">
                {formatDateTime(connection.last_successful_sync_at)}
              </dd>
            </div>
            <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
              <dt className="text-xs font-medium text-slate-500">Son hata</dt>
              <dd className="mt-0.5 text-sm font-semibold text-slate-900">
                {connection.last_error?.trim() ? connection.last_error : "—"}
              </dd>
            </div>
          </dl>

          {metrics ? (
            <div className="space-y-3 border-t border-slate-100 pt-4">
              <h3 className="text-sm font-semibold text-slate-900">Entegrasyon izleme</h3>
              <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {(
                  [
                    ["Alınan", metrics.fetched],
                    ["Oluşturulan", metrics.created],
                    ["Güncellenen", metrics.updated],
                    ["Atlanan", metrics.skipped],
                    ["Hatalı", metrics.failed],
                    ["API cevap süresi", formatMs(metrics.api_duration_ms)],
                    [
                      "Rate limit",
                      metrics.rate_limit?.limited
                        ? metrics.rate_limit.message || "Sınırda"
                        : "Normal",
                    ],
                    ["Son senkron süresi", formatMs(metrics.last_sync_duration_ms)],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-slate-100 px-3 py-2">
                    <dt className="text-xs text-slate-500">{label}</dt>
                    <dd className="mt-0.5 text-sm font-semibold text-slate-900">{value}</dd>
                  </div>
                ))}
              </dl>
              {monitoring && monitoring.open_conflicts > 0 ? (
                <p className="text-sm text-amber-800">Açık çakışma: {monitoring.open_conflicts}</p>
              ) : null}
            </div>
          ) : null}

          {conflicts.length > 0 ? (
            <div className="space-y-3 border-t border-slate-100 pt-4">
              <h3 className="text-sm font-semibold text-slate-900">Senkronizasyon çakışmaları</h3>
              <ul className="space-y-3">
                {conflicts.map((conflict) => (
                  <li
                    key={conflict.id}
                    className="rounded-lg border border-amber-100 bg-amber-50/40 px-3 py-3"
                  >
                    <p className="text-sm font-medium text-slate-900">
                      {CONFLICT_TYPE_LABEL[conflict.conflict_type] ?? conflict.conflict_type}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">{conflict.message}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {conflict.entity_type}
                      {conflict.external_id ? ` · ${conflict.external_id}` : ""}
                    </p>
                    <div className="mt-2">
                      <Input
                        label="Alan (isteğe bağlı / skip için zorunlu)"
                        value={skipFieldByConflict[conflict.id] ?? ""}
                        onChange={(e) =>
                          setSkipFieldByConflict((prev) => ({
                            ...prev,
                            [conflict.id]: e.target.value,
                          }))
                        }
                        placeholder="ör. description"
                      />
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {RESOLUTION_ACTIONS.map((action) => (
                        <Button
                          key={action.value}
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => void onResolve(conflict, action.value)}
                        >
                          {action.label}
                        </Button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <Select
            label="Otomatik eşitleme sıklığı"
            options={FREQUENCY_OPTIONS}
            value={syncFrequency}
            onChange={(e) => void onChangeFrequency(e.target.value as SyncFrequency)}
            disabled={busy}
          />

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void onManualSync()} loading={busy}>
              Manuel eşitle
            </Button>
            <Button variant="outline" onClick={onReconnect} disabled={busy}>
              Kimlik bilgilerini güncelle
            </Button>
            <Button variant="ghost" onClick={() => void onDisconnect()} disabled={busy}>
              Bağlantıyı kaldır
            </Button>
          </div>
        </div>
      ) : null}

      {step === "credentials" ? (
        <div className="space-y-4 border-t border-slate-100 pt-4">
          <p className="text-sm text-slate-600">
            1. Adım — KolayBi API anahtarı ve Channel ID girin, ardından bağlantıyı test edin.
          </p>
          <Input
            label="API anahtarı"
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            hint={
              connection?.has_credentials
                ? `Kayıtlı anahtar ipucu: …${connection.key_hint}`
                : "Geliştirme için mock- ile başlayan anahtar kullanılabilir."
            }
          />
          <Input
            label="Channel ID"
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
            autoComplete="off"
          />
          <Button onClick={() => void onSaveAndTest()} loading={busy}>
            Kaydet ve bağlantıyı test et
          </Button>
        </div>
      ) : null}

      {step === "companies" ? (
        <div className="space-y-4 border-t border-slate-100 pt-4">
          <p className="text-sm text-slate-600">2. Adım — Eşitlemek istediğiniz KolayBi şirketini seçin.</p>
          <Select
            label="KolayBi şirketi"
            options={companyOptions}
            value={selectedCompanyId}
            onChange={(e) => setSelectedCompanyId(e.target.value)}
            placeholder="Şirket seçin"
            disabled={busy || companyOptions.length === 0}
          />
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void onSelectCompany()} loading={busy} disabled={!selectedCompanyId}>
              Şirketi seç ve devam et
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={async () => {
                if (!connection) return;
                setBusy(true);
                const result = await listCompanies(connection.id);
                setBusy(false);
                if (!result.ok) {
                  toast({
                    title: "Şirketler yenilenemedi",
                    description: result.error.message,
                    tone: "error",
                  });
                  return;
                }
                setCompanies(result.data);
              }}
            >
              Şirketleri yenile
            </Button>
          </div>
        </div>
      ) : null}

      {step === "settings" ? (
        <div className="space-y-4 border-t border-slate-100 pt-4">
          <p className="text-sm text-slate-600">
            3. Adım — Senkronizasyon sıklığını belirleyin ve ilk eşitlemeyi başlatın.
          </p>
          <Select
            label="Otomatik eşitleme sıklığı"
            options={FREQUENCY_OPTIONS}
            value={syncFrequency}
            onChange={(e) => setSyncFrequency(e.target.value as SyncFrequency)}
            disabled={busy}
          />
          <Button onClick={() => void onSaveSettingsAndSync()} loading={busy}>
            Kaydet ve ilk eşitlemeyi başlat
          </Button>
        </div>
      ) : null}
    </section>
  );
}
