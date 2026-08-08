"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { cn } from "@/lib/cn";
import type { AppError } from "@/lib/errors";
import {
  IMPORTANCE_GROUPS,
  alertImportance,
  fetchDashboardAlerts,
  fetchNotificationPreferences,
  markAlertRead,
  markAllAlertsRead,
  normalizeAlertsPayload,
  updateNotificationPreferences,
  type DashboardAlert,
  type NotificationPreferences,
} from "@/lib/notifications/api";

const TYPE_LABELS: Record<string, string> = {
  TASK_DUE: "Görev vadesi",
  TASK_OVERDUE: "Gecikmiş görev",
  TASK_ASSIGNED: "Atanan görev",
  PROMISE_DUE: "Söz vadesi",
  PROMISE_BROKEN: "Bozulan söz",
  HIGH_RISK_CUSTOMER: "Yüksek risk",
  CRITICAL_CUSTOMER: "Kritik müşteri",
  IMPORT_COMPLETED: "İçe aktarma",
  IMPORT_FAILED: "İçe aktarma hatası",
  CASH_GAP: "Nakit açığı",
};

function formatWhen(iso: string): string {
  try {
    return new Intl.DateTimeFormat("tr-TR", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

type CustomerGroup = {
  key: string;
  customerId: number | null;
  customerName: string;
  alerts: DashboardAlert[];
};

function groupByCustomer(alerts: DashboardAlert[]): CustomerGroup[] {
  const map = new Map<string, CustomerGroup>();
  for (const alert of alerts) {
    const cid = alert.customer_id ?? null;
    const key = cid != null ? `c-${cid}` : `a-${alert.id}`;
    const existing = map.get(key);
    if (existing) {
      existing.alerts.push(alert);
    } else {
      map.set(key, {
        key,
        customerId: cid,
        customerName: alert.customer_name || "Diğer",
        alerts: [alert],
      });
    }
  }
  return Array.from(map.values());
}

export function NotificationsView() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<DashboardAlert[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [marking, setMarking] = useState(false);
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [prefsOpen, setPrefsOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const [result, prefRes] = await Promise.all([
      fetchDashboardAlerts({ unread: filter === "unread", limit: 100 }),
      fetchNotificationPreferences(),
    ]);
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError(null);
    const { alerts: list, unreadCount: unread, groupByCustomer } = normalizeAlertsPayload(
      result.data,
    );
    setAlerts(list);
    setUnreadCount(unread);
    if (prefRes.ok) {
      setPrefs(prefRes.data);
    } else {
      setPrefs({
        muted_types: [],
        mute_info: false,
        mute_system: false,
        group_by_customer: groupByCustomer,
      });
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  const byImportance = useMemo(() => {
    const buckets: Record<string, DashboardAlert[]> = {
      critical: [],
      action: [],
      info: [],
      system: [],
    };
    for (const alert of alerts) {
      buckets[alertImportance(alert)].push(alert);
    }
    return buckets;
  }, [alerts]);

  async function onOpen(alert: DashboardAlert) {
    if (!alert.is_read) {
      const res = await markAlertRead(alert.id);
      if (res.ok) {
        setAlerts((prev) =>
          prev.map((a) => (a.id === alert.id ? { ...a, is_read: true } : a)),
        );
        setUnreadCount((c) => Math.max(0, c - 1));
      }
    }
    if (alert.href) router.push(alert.href);
  }

  async function onMarkAll() {
    setMarking(true);
    const res = await markAllAlertsRead();
    setMarking(false);
    if (res.ok) {
      // NP-462 — critical stays unread / visible.
      setAlerts((prev) =>
        prev.map((a) =>
          alertImportance(a) === "critical" ? a : { ...a, is_read: true },
        ),
      );
      void load();
    }
  }

  async function savePrefs(next: Partial<NotificationPreferences>) {
    const res = await updateNotificationPreferences(next);
    if (!res.ok) return;
    setPrefs(res.data);
    void load();
  }

  if (loading && alerts.length === 0) {
    return <LoadingSkeleton lines={6} />;
  }

  if (error) {
    return <ErrorState error={error} onRetry={() => void load()} />;
  }

  const groupEnabled = prefs?.group_by_customer !== false;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl tracking-tight text-foreground">Bildirimler</h1>
          <p className="mt-1 text-sm text-muted">
            {unreadCount > 0 ? `${unreadCount} okunmamış bildirim` : "Tüm bildirimler okundu"}
            {" · Kritik bildirimler korunur"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-[var(--radius-md)] border border-border-default p-0.5 text-sm">
            <button
              type="button"
              onClick={() => setFilter("all")}
              className={cn(
                "rounded-[calc(var(--radius-md)-2px)] px-3 py-1.5",
                filter === "all" ? "bg-primary text-primary-foreground" : "text-muted",
              )}
            >
              Tümü
            </button>
            <button
              type="button"
              onClick={() => setFilter("unread")}
              className={cn(
                "rounded-[calc(var(--radius-md)-2px)] px-3 py-1.5",
                filter === "unread" ? "bg-primary text-primary-foreground" : "text-muted",
              )}
            >
              Okunmamış
            </button>
          </div>
          <Button type="button" variant="outline" onClick={() => setPrefsOpen((v) => !v)}>
            Tercihler
          </Button>
          {unreadCount > 0 ? (
            <Button variant="outline" disabled={marking} onClick={() => void onMarkAll()}>
              Tümünü okundu yap
            </Button>
          ) : null}
        </div>
      </div>

      {prefsOpen && prefs ? (
        <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 text-sm">
          <h2 className="font-semibold text-foreground">Bildirim tercihleri</h2>
          <p className="mt-1 text-xs text-muted">Kritik olaylar asla gizlenmez.</p>
          <div className="mt-3 space-y-2">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={prefs.group_by_customer}
                onChange={(e) => void savePrefs({ group_by_customer: e.target.checked })}
              />
              Aynı müşteri bildirimlerini grupla
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={prefs.mute_info}
                onChange={(e) => void savePrefs({ mute_info: e.target.checked })}
              />
              Bilgilendirme bildirimlerini gizle
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={prefs.mute_system}
                onChange={(e) => void savePrefs({ mute_system: e.target.checked })}
              />
              Sistem bildirimlerini gizle
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={prefs.muted_types.includes("PROMISE_DUE")}
                onChange={(e) => {
                  const next = new Set(prefs.muted_types);
                  if (e.target.checked) next.add("PROMISE_DUE");
                  else next.delete("PROMISE_DUE");
                  void savePrefs({ muted_types: Array.from(next) });
                }}
              />
              Ödeme sözü vadesi hatırlatmalarını gizle
            </label>
          </div>
        </section>
      ) : null}

      {alerts.length === 0 ? (
        <EmptyState
          title="Bildirim yok"
          description={
            filter === "unread"
              ? "Okunmamış bildiriminiz bulunmuyor."
              : "Henüz bir bildirim oluşturulmadı."
          }
        />
      ) : (
        <div className="space-y-6">
          {IMPORTANCE_GROUPS.map((group) => {
            const items = byImportance[group.id];
            if (!items.length) return null;
            const clusters = groupEnabled ? groupByCustomer(items) : null;
            return (
              <section key={group.id}>
                <h2 className="mb-2 text-sm font-semibold text-foreground">
                  {group.label}
                  <span className="ml-2 text-xs font-normal text-muted">{items.length}</span>
                </h2>
                <ul className="divide-y divide-border-default rounded-[var(--radius-lg)] border border-border-default bg-surface-primary">
                  {clusters
                    ? clusters.map((cluster) => {
                        const multi = cluster.alerts.length > 1 && cluster.customerId != null;
                        const open = expandedGroups[cluster.key] ?? group.id === "critical";
                        if (!multi) {
                          return (
                            <li key={cluster.key}>
                              <AlertRow
                                alert={cluster.alerts[0]}
                                onOpen={() => void onOpen(cluster.alerts[0])}
                              />
                            </li>
                          );
                        }
                        return (
                          <li key={cluster.key} className="px-3 py-3">
                            <button
                              type="button"
                              className="flex w-full items-center justify-between gap-2 text-left"
                              onClick={() =>
                                setExpandedGroups((prev) => ({
                                  ...prev,
                                  [cluster.key]: !open,
                                }))
                              }
                            >
                              <span className="text-sm font-semibold text-foreground">
                                {cluster.customerName} için {cluster.alerts.length} yeni gelişme
                              </span>
                              <span className="text-xs text-muted">{open ? "Gizle" : "Aç"}</span>
                            </button>
                            {open ? (
                              <ul className="mt-2 divide-y divide-border-default border-t border-border-default">
                                {cluster.alerts.map((alert) => (
                                  <li key={alert.id}>
                                    <AlertRow alert={alert} onOpen={() => void onOpen(alert)} />
                                  </li>
                                ))}
                              </ul>
                            ) : null}
                          </li>
                        );
                      })
                    : items.map((alert) => (
                        <li key={alert.id}>
                          <AlertRow alert={alert} onOpen={() => void onOpen(alert)} />
                        </li>
                      ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AlertRow({ alert, onOpen }: { alert: DashboardAlert; onOpen: () => void }) {
  const actions = alert.actions?.length
    ? alert.actions
    : alert.href
      ? [{ label: "Kayda git", href: alert.href }]
      : [];

  return (
    <div
      className={cn(
        "flex w-full flex-col gap-2 px-3 py-3 transition hover:bg-surface-secondary/50",
        !alert.is_read && "bg-primary/[0.03]",
      )}
    >
      <button type="button" onClick={onOpen} className="text-left">
        <div className="flex flex-wrap items-center gap-2">
          {!alert.is_read ? (
            <span className="bg-primary size-2 shrink-0 rounded-full" aria-hidden />
          ) : (
            <span className="size-2 shrink-0" aria-hidden />
          )}
          <span className="text-sm font-semibold text-foreground">{alert.title}</span>
          {alert.notification_type ? (
            <span className="rounded bg-surface-secondary px-1.5 py-0.5 text-[11px] text-muted">
              {TYPE_LABELS[alert.notification_type] ?? alert.notification_type}
            </span>
          ) : null}
        </div>
        {alert.body ? <p className="mt-1 pl-4 text-sm text-muted">{alert.body}</p> : null}
        <time className="mt-1 block pl-4 text-xs text-subtle" dateTime={alert.created_at}>
          {formatWhen(alert.created_at)}
        </time>
      </button>
      {actions.length ? (
        <div className="flex flex-wrap gap-2 pl-4">
          {actions.map((action) => (
            <Link
              key={`${action.label}-${action.href}`}
              href={action.href}
              className="inline-flex h-8 items-center rounded-[var(--radius-md)] border border-border-default px-2.5 text-xs font-semibold hover:bg-surface-secondary"
              onClick={() => {
                if (!alert.is_read) void markAlertRead(alert.id);
              }}
            >
              {action.label}
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  );
}
