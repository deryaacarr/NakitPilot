"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import type { AppError } from "@/lib/errors";
import {
  fetchDashboardAlerts,
  markAlertRead,
  markAllAlertsRead,
  normalizeAlertsPayload,
  type DashboardAlert,
} from "@/lib/notifications/api";
import { cn } from "@/lib/cn";

const TYPE_LABELS: Record<string, string> = {
  TASK_DUE: "Görev vadesi",
  TASK_OVERDUE: "Gecikmiş görev",
  PROMISE_DUE: "Söz vadesi",
  PROMISE_BROKEN: "Bozulan söz",
  HIGH_RISK_CUSTOMER: "Yüksek risk",
  IMPORT_COMPLETED: "İçe aktarma",
  IMPORT_FAILED: "İçe aktarma hatası",
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

export function NotificationsView() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<DashboardAlert[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [marking, setMarking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchDashboardAlerts({
      unread: filter === "unread",
      limit: 100,
    });
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError(null);
    const { alerts: list, unreadCount: unread } = normalizeAlertsPayload(result.data);
    setAlerts(list);
    setUnreadCount(unread);
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

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
      setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })));
      setUnreadCount(0);
      if (filter === "unread") setAlerts([]);
    }
  }

  if (loading && alerts.length === 0) {
    return <LoadingSkeleton lines={6} />;
  }

  if (error) {
    return <ErrorState error={error} onRetry={() => void load()} />;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl tracking-tight text-slate-900">Bildirimler</h1>
          <p className="mt-1 text-sm text-slate-500">
            {unreadCount > 0 ? `${unreadCount} okunmamış bildirim` : "Tüm bildirimler okundu"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-slate-200 p-0.5 text-sm">
            <button
              type="button"
              onClick={() => setFilter("all")}
              className={cn(
                "rounded-md px-3 py-1.5",
                filter === "all" ? "bg-slate-900 text-white" : "text-slate-600",
              )}
            >
              Tümü
            </button>
            <button
              type="button"
              onClick={() => setFilter("unread")}
              className={cn(
                "rounded-md px-3 py-1.5",
                filter === "unread" ? "bg-slate-900 text-white" : "text-slate-600",
              )}
            >
              Okunmamış
            </button>
          </div>
          {unreadCount > 0 ? (
            <Button variant="outline" disabled={marking} onClick={() => void onMarkAll()}>
              Tümünü okundu yap
            </Button>
          ) : null}
        </div>
      </div>

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
        <ul className="divide-y divide-slate-100 border-y border-slate-100">
          {alerts.map((alert) => (
            <li key={alert.id}>
              <button
                type="button"
                onClick={() => void onOpen(alert)}
                className={cn(
                  "flex w-full flex-col gap-1 px-1 py-4 text-left transition hover:bg-slate-50",
                  !alert.is_read && "bg-brand/[0.03]",
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  {!alert.is_read ? (
                    <span className="bg-brand size-2 shrink-0 rounded-full" aria-hidden />
                  ) : (
                    <span className="size-2 shrink-0" aria-hidden />
                  )}
                  <span className="text-sm font-semibold text-slate-900">{alert.title}</span>
                  {alert.notification_type ? (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
                      {TYPE_LABELS[alert.notification_type] ?? alert.notification_type}
                    </span>
                  ) : null}
                </div>
                {alert.body ? (
                  <p className="pl-4 text-sm text-slate-600">{alert.body}</p>
                ) : null}
                <div className="flex flex-wrap items-center gap-3 pl-4 text-xs text-slate-400">
                  <time dateTime={alert.created_at}>{formatWhen(alert.created_at)}</time>
                  {alert.href ? (
                    <Link
                      href={alert.href}
                      onClick={(e) => e.stopPropagation()}
                      className="text-brand hover:underline"
                    >
                      Kayda git
                    </Link>
                  ) : null}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
