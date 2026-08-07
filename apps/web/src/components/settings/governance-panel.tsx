"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

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
    const [
      r,
      s,
      ret,
      a,
      e,
      acc,
      inv,
      ssoRes,
      m,
    ] = await Promise.all([
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
    <section id="governance" className="space-y-6 rounded-xl border border-slate-200 bg-white p-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">Kurumsal yetki &amp; KVKK</h2>
        <p className="mt-1 text-xs text-slate-500">
          Özel roller, oturumlar, SSO, saklama, dışa aktarma, silme ve veri envanteri.
        </p>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {message ? <p className="text-sm text-teal-800">{message}</p> : null}

      <Block title="Özel roller (NP-300)">
        <ul className="space-y-1 text-sm">
          {roles.map((role) => (
            <li key={String(role.id)}>
              {String(role.name)}
              <span className="text-slate-500">
                {" "}
                · {(role.permissions as string[] | undefined)?.length ?? 0} izin
              </span>
            </li>
          ))}
          {roles.length === 0 ? <li className="text-slate-500">Rol yok / yetki yetersiz</li> : null}
        </ul>
      </Block>

      <Block title="Aktif oturumlar (NP-305)">
        <ul className="space-y-2 text-sm">
          {sessions.map((s) => (
            <li key={String(s.id)} className="flex items-center justify-between gap-2">
              <span>
                {String(s.device_label)} · {String(s.ip_address ?? "—")}
                {s.is_suspicious ? " · şüpheli" : ""}
              </span>
              <button
                type="button"
                className="text-rose-700 underline"
                onClick={() => void revokeSession(Number(s.id)).then(() => reload())}
              >
                Çıkış yaptır
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="mt-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm"
          onClick={() =>
            void revokeAllSessions().then((res) => {
              if (res.ok) setMessage(`${res.data.revoked_count} oturum sonlandırıldı`);
              void reload();
            })
          }
        >
          Tüm oturumları sonlandır
        </button>
      </Block>

      <Block title="SSO (NP-304)">
        <ul className="text-sm space-y-1">
          {sso.map((p) => (
            <li key={String(p.id)}>
              {String(p.name)} · {String(p.protocol)} · {p.is_enabled ? "aktif" : "pasif"}
            </li>
          ))}
          {sso.length === 0 ? (
            <li className="text-slate-500">Enterprise pakette SAML / OIDC / Google / Entra</li>
          ) : null}
        </ul>
      </Block>

      <Block title="Saklama politikası (NP-310)">
        {retention ? (
          <dl className="grid gap-2 sm:grid-cols-2 text-sm">
            {Object.entries((retention.labels as Record<string, string>) || {}).map(([key, label]) => (
              <div key={key}>
                <dt className="text-xs text-slate-500">{label}</dt>
                <dd>{String(retention[key])} gün</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-sm text-slate-500">Yüklenemedi (paket yetkisi gerekebilir).</p>
        )}
      </Block>

      <Block title="Veri dışa aktarma (NP-311)">
        <button
          type="button"
          className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm text-white"
          onClick={() =>
            void startExport(["customers", "invoices", "payments", "tasks", "audit"]).then((res) => {
              if (!res.ok) setError(res.error.message);
              else setMessage("Dışa aktarma hazır");
              void reload();
            })
          }
        >
          Dışa aktarımı başlat
        </button>
        <ul className="mt-2 space-y-1 text-sm">
          {exports.slice(0, 5).map((job) => (
            <li key={String(job.id)}>
              #{String(job.id)} · {String(job.status)}
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Maskeleme örneği (NP-313)">
        {mask ? (
          <ul className="text-sm space-y-1">
            <li>Telefon: {mask.phone}</li>
            <li>E-posta: {mask.email}</li>
            <li>Vergi no: {mask.tax_number}</li>
          </ul>
        ) : null}
      </Block>

      <Block title="Onay kuyruğu (NP-303)">
        <ul className="text-sm space-y-1">
          {approvals.slice(0, 5).map((a) => (
            <li key={String(a.id)}>
              {String(a.action_type)} · {String(a.status)}
            </li>
          ))}
          {approvals.length === 0 ? <li className="text-slate-500">Bekleyen onay yok</li> : null}
        </ul>
      </Block>

      <Block title="Veri erişim raporu (NP-314)">
        <ul className="text-sm space-y-1 max-h-40 overflow-auto">
          {access.slice(0, 10).map((row) => (
            <li key={String(row.id)}>
              {String(row.actor_email ?? row.actor_id)} · {String(row.action)} ·{" "}
              {String(row.resource_type)}:{String(row.resource_id)}
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Veri işleme envanteri (NP-315)">
        <ul className="text-sm space-y-1 max-h-40 overflow-auto">
          {inventory.map((item) => (
            <li key={String(item.id)}>
              <span className="font-medium">{String(item.field_key)}</span>
              <span className="text-slate-500">
                {" "}
                · {String(item.data_type)} · {String(item.retention_days)}g
              </span>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Organizasyon silme (NP-312)">
        <button
          type="button"
          className="rounded-lg border border-rose-200 px-3 py-1.5 text-sm text-rose-700"
          onClick={() =>
            void requestDeletion("Yönetici talebi").then((res) => {
              if (!res.ok) setError(res.error.message);
              else setMessage(`Silme talebi oluşturuldu — bekleme: ${String(res.data.waiting_until)}`);
            })
          }
        >
          Silme talebi oluştur (bekleme süresi ile)
        </button>
      </Block>
    </section>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-t border-slate-100 pt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}
