"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Surface } from "@/components/ui/surface";
import {
  fetchAccessReport,
  fetchApprovals,
  fetchCustomRoles,
  fetchExports,
  fetchInventory,
  fetchRetention,
  fetchSessions,
  fetchSsoProviders,
  maskPreview,
  requestDeletion,
  revokeAllSessions,
  revokeSession,
  startExport,
} from "@/lib/governance/api";

export function GovernancePanel() {
  const [roles, setRoles] = useState<Array<Record<string, unknown>>>([]);
  const [sessions, setSessions] = useState<Array<Record<string, unknown>>>([]);
  const [retention, setRetention] = useState<Record<string, unknown> | null>(null);
  const [approvals, setApprovals] = useState<Array<Record<string, unknown>>>([]);
  const [exports, setExports] = useState<Array<Record<string, unknown>>>([]);
  const [access, setAccess] = useState<Array<Record<string, unknown>>>([]);
  const [inventory, setInventory] = useState<Array<Record<string, unknown>>>([]);
  const [sso, setSso] = useState<Array<Record<string, unknown>>>([]);
  const [mask, setMask] = useState<{ phone: string; email: string; tax_number: string } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const [r, s, ret, a, e, acc, inv, ssoRes, m] = await Promise.all([
      fetchCustomRoles(),
      fetchSessions(),
      fetchRetention(),
      fetchApprovals(),
      fetchExports(),
      fetchAccessReport(),
      fetchInventory(),
      fetchSsoProviders(),
      maskPreview("05321234567", "mehmet@firma.com", "1234567890"),
    ]);
    if (r.ok) setRoles(r.data.results);
    if (s.ok) setSessions(s.data.results);
    if (ret.ok) setRetention(ret.data);
    else if (ret.error) setError(ret.error.message);
    if (a.ok) setApprovals(a.data.results);
    if (e.ok) setExports(e.data.results);
    if (acc.ok) setAccess(acc.data.results);
    if (inv.ok) setInventory(inv.data.results);
    if (ssoRes.ok) setSso(ssoRes.data.results);
    if (m.ok) setMask(m.data);
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <Surface as="section" id="users" className="space-y-6">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Kurumsal yetki &amp; KVKK</h2>
        <p className="mt-1 text-xs text-muted">
          Özel roller, oturumlar, SSO, saklama, dışa aktarma, silme ve veri envanteri.
        </p>
      </div>
      {error ? <p className="text-sm text-danger-foreground">{error}</p> : null}
      {message ? <p className="text-sm text-success-foreground">{message}</p> : null}

      <Block title="Özel roller (NP-300)">
        <ul className="space-y-1 text-sm text-foreground">
          {roles.map((role) => (
            <li key={String(role.id)}>
              {String(role.name)}
              <span className="text-muted">
                {" "}
                · {(role.permissions as string[] | undefined)?.length ?? 0} izin
              </span>
            </li>
          ))}
          {roles.length === 0 ? <li className="text-muted">Rol yok / yetki yetersiz</li> : null}
        </ul>
      </Block>

      <Block title="Aktif oturumlar (NP-305)">
        <ul className="space-y-2 text-sm text-foreground">
          {sessions.map((s) => (
            <li key={String(s.id)} className="flex items-center justify-between gap-2">
              <span>
                {String(s.device_label)} · {String(s.ip_address ?? "—")}
                {s.is_suspicious ? " · şüpheli" : ""}
              </span>
              <button
                type="button"
                className="min-h-11 text-danger-foreground underline"
                onClick={() => void revokeSession(Number(s.id)).then(() => reload())}
              >
                Çıkış yaptır
              </button>
            </li>
          ))}
        </ul>
        <Button
          type="button"
          variant="outline"
          className="mt-2"
          onClick={() =>
            void revokeAllSessions().then((res) => {
              if (res.ok) setMessage(`${res.data.revoked_count} oturum sonlandırıldı`);
              void reload();
            })
          }
        >
          Tüm oturumları sonlandır
        </Button>
      </Block>

      <Block title="SSO (NP-304)">
        <ul className="space-y-1 text-sm text-foreground">
          {sso.map((p) => (
            <li key={String(p.id)}>
              {String(p.name)} · {String(p.protocol)} · {p.is_enabled ? "aktif" : "pasif"}
            </li>
          ))}
          {sso.length === 0 ? (
            <li className="text-muted">Enterprise pakette SAML / OIDC / Google / Entra</li>
          ) : null}
        </ul>
      </Block>

      <Block title="Saklama politikası (NP-310)">
        {retention ? (
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            {Object.entries((retention.labels as Record<string, string>) || {}).map(
              ([key, label]) => (
                <div key={key}>
                  <dt className="text-xs text-muted">{label}</dt>
                  <dd className="text-foreground">{String(retention[key])} gün</dd>
                </div>
              ),
            )}
          </dl>
        ) : (
          <p className="text-sm text-muted">Yüklenemedi (paket yetkisi gerekebilir).</p>
        )}
      </Block>

      <Block title="Veri dışa aktarma (NP-311)">
        <Button
          type="button"
          onClick={() =>
            void startExport(["customers", "invoices", "payments", "tasks", "audit"]).then(
              (res) => {
                if (!res.ok) setError(res.error.message);
                else setMessage("Dışa aktarma hazır");
                void reload();
              },
            )
          }
        >
          Dışa aktarımı başlat
        </Button>
        <ul className="mt-2 space-y-1 text-sm text-foreground">
          {exports.slice(0, 5).map((job) => (
            <li key={String(job.id)}>
              #{String(job.id)} · {String(job.status)}
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Maskeleme örneği (NP-313)">
        {mask ? (
          <ul className="space-y-1 text-sm text-foreground">
            <li>Telefon: {mask.phone}</li>
            <li>E-posta: {mask.email}</li>
            <li>Vergi no: {mask.tax_number}</li>
          </ul>
        ) : null}
      </Block>

      <Block title="Onay kuyruğu (NP-303)">
        <ul className="space-y-1 text-sm text-foreground">
          {approvals.slice(0, 5).map((a) => (
            <li key={String(a.id)}>
              {String(a.action_type)} · {String(a.status)}
            </li>
          ))}
          {approvals.length === 0 ? <li className="text-muted">Bekleyen onay yok</li> : null}
        </ul>
      </Block>

      <Block title="Veri erişim raporu (NP-314)">
        <ul className="max-h-40 space-y-1 overflow-auto text-sm text-foreground">
          {access.slice(0, 10).map((row) => (
            <li key={String(row.id)}>
              {String(row.actor_email ?? row.actor_id)} · {String(row.action)} ·{" "}
              {String(row.resource_type)}:{String(row.resource_id)}
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Veri işleme envanteri (NP-315)">
        <ul className="max-h-40 space-y-1 overflow-auto text-sm text-foreground">
          {inventory.map((item) => (
            <li key={String(item.id)}>
              <span className="font-medium">{String(item.field_key)}</span>
              <span className="text-muted">
                {" "}
                · {String(item.data_type)} · {String(item.retention_days)}g
              </span>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Organizasyon silme (NP-312)">
        <Button
          type="button"
          variant="outline"
          className="border-danger/40 text-danger-foreground"
          onClick={() =>
            void requestDeletion("Yönetici talebi").then((res) => {
              if (!res.ok) setError(res.error.message);
              else
                setMessage(
                  `Silme talebi oluşturuldu — bekleme: ${String(res.data.waiting_until)}`,
                );
            })
          }
        >
          Silme talebi oluştur (bekleme süresi ile)
        </Button>
      </Block>
    </Surface>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-t border-border-default pt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-subtle">{title}</h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}
