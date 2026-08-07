"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ErrorState } from "@/components/errors/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SkeletonBlock } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { createApiKey, listApiKeyScopes, listApiKeys, revokeApiKey } from "@/lib/api-keys/api";
import type { ApiKey, ScopeOption } from "@/lib/api-keys/types";
import { cn } from "@/lib/cn";

function formatDateTime(value: string | null) {
  if (!value) return "Hiç kullanılmadı";
  try {
    return new Intl.DateTimeFormat("tr-TR", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function unwrapKeys(data: { results: ApiKey[] } | ApiKey[]): ApiKey[] {
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

export function ApiKeysPanel() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [scopes, setScopes] = useState<ScopeOption[]>([]);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    setForbidden(false);
    const [keysResult, scopesResult] = await Promise.all([listApiKeys(), listApiKeyScopes()]);
    setLoading(false);
    if (!keysResult.ok) {
      if (keysResult.error.kind === "forbidden") {
        setForbidden(true);
        return;
      }
      setLoadError(keysResult.error.message);
      return;
    }
    setKeys(unwrapKeys(keysResult.data));
    if (scopesResult.ok) {
      setScopes(scopesResult.data.scopes);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const activeKeys = useMemo(() => keys.filter((k) => k.is_active), [keys]);
  const revokedKeys = useMemo(() => keys.filter((k) => !k.is_active), [keys]);

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope],
    );
  };

  const onCreate = async () => {
    if (!name.trim()) {
      toast({ title: "İsim gerekli", description: "API anahtarına bir isim verin.", tone: "error" });
      return;
    }
    if (selectedScopes.length === 0) {
      toast({
        title: "Yetki alanı gerekli",
        description: "En az bir scope seçin.",
        tone: "error",
      });
      return;
    }
    setBusy(true);
    const result = await createApiKey({ name: name.trim(), scopes: selectedScopes });
    setBusy(false);
    if (!result.ok) {
      toast({ title: "Anahtar oluşturulamadı", description: result.error.message, tone: "error" });
      return;
    }
    setCreatedSecret(result.data.key);
    setName("");
    setSelectedScopes([]);
    toast({ title: "API anahtarı oluşturuldu", tone: "success" });
    await load();
  };

  const onCopy = async () => {
    if (!createdSecret) return;
    try {
      await navigator.clipboard.writeText(createdSecret);
      toast({ title: "Panoya kopyalandı", tone: "success" });
    } catch {
      toast({ title: "Kopyalanamadı", tone: "error" });
    }
  };

  const onRevoke = async (key: ApiKey) => {
    if (!window.confirm(`“${key.name}” anahtarı iptal edilsin mi? Bu işlem geri alınamaz.`)) {
      return;
    }
    setBusy(true);
    const result = await revokeApiKey(key.id);
    setBusy(false);
    if (!result.ok) {
      toast({ title: "İptal edilemedi", description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "Anahtar iptal edildi", tone: "success" });
    await load();
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
          message: "API anahtarlarını yalnızca organizasyon sahibi veya yöneticisi yönetebilir.",
          status: 403,
        }}
      />
    );
  }

  if (loadError) {
    return <ErrorState error={loadError} onRetry={() => void load()} />;
  }

  return (
    <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div>
        <h2 className="font-serif text-2xl tracking-tight text-slate-900">API anahtarları</h2>
        <p className="mt-1 text-sm text-slate-600">
          Dış sistemlerin NakitPilot’a bağlanması için anahtar oluşturun. Tam anahtar yalnızca
          oluşturulduğu anda bir kez gösterilir.
        </p>
      </div>

      {createdSecret ? (
        <div className="space-y-3 rounded-lg border border-teal-200 bg-teal-50/60 px-4 py-3">
          <p className="text-sm font-semibold text-teal-900">Yeni anahtar — şimdi kopyalayın</p>
          <p className="text-xs text-teal-800">
            Bu değer bir daha gösterilmeyecek. Güvenli bir yerde saklayın.
          </p>
          <code className="block break-all rounded-md bg-white px-3 py-2 text-sm text-slate-900">
            {createdSecret}
          </code>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => void onCopy()}>
              Kopyala
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setCreatedSecret(null)}>
              Gizle
            </Button>
          </div>
        </div>
      ) : null}

      <div className="space-y-3 border-t border-slate-100 pt-4">
        <h3 className="text-sm font-semibold text-slate-900">Yeni anahtar</h3>
        <Input
          label="İsim"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="ör. ERP entegrasyonu"
        />
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-slate-700">Yetki alanları</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {scopes.map((scope) => {
              const checked = selectedScopes.includes(scope.value);
              return (
                <label
                  key={scope.value}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                    checked ? "border-teal-300 bg-teal-50/50" : "border-slate-200 bg-white",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleScope(scope.value)}
                    className="rounded border-slate-300"
                  />
                  <span className="font-mono text-xs text-slate-800">{scope.label}</span>
                </label>
              );
            })}
          </div>
        </fieldset>
        <Button onClick={() => void onCreate()} loading={busy}>
          Anahtar oluştur
        </Button>
      </div>

      <div className="space-y-3 border-t border-slate-100 pt-4">
        <h3 className="text-sm font-semibold text-slate-900">Aktif anahtarlar</h3>
        {activeKeys.length === 0 ? (
          <p className="text-sm text-slate-500">Henüz aktif anahtar yok.</p>
        ) : (
          <ul className="space-y-3">
            {activeKeys.map((key) => (
              <li
                key={key.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-100 px-3 py-3"
              >
                <div>
                  <p className="text-sm font-semibold text-slate-900">{key.name}</p>
                  <p className="mt-0.5 font-mono text-xs text-slate-500">{key.display_prefix}…</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Son kullanım: {formatDateTime(key.last_used_at)}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {key.scopes.map((scope) => (
                      <span
                        key={scope}
                        className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700"
                      >
                        {scope}
                      </span>
                    ))}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="danger"
                  disabled={busy}
                  onClick={() => void onRevoke(key)}
                >
                  İptal et
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {revokedKeys.length > 0 ? (
        <div className="space-y-2 border-t border-slate-100 pt-4">
          <h3 className="text-sm font-semibold text-slate-500">İptal edilenler</h3>
          <ul className="space-y-2">
            {revokedKeys.map((key) => (
              <li key={key.id} className="rounded-lg border border-slate-100 px-3 py-2 opacity-70">
                <p className="text-sm text-slate-700">{key.name}</p>
                <p className="font-mono text-xs text-slate-500">{key.display_prefix}…</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
