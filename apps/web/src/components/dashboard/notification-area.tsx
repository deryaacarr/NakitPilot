"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import {
  fetchDashboardAlerts,
  markAlertRead,
  markAllAlertsRead,
  normalizeAlertsPayload,
  type DashboardAlert,
} from "@/lib/notifications/api";

import { useDashboard } from "./dashboard-context";

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffMin = Math.round((Date.now() - then) / 60_000);
  if (diffMin < 1) return "şimdi";
  if (diffMin < 60) return `${diffMin} dk`;
  const hours = Math.round(diffMin / 60);
  if (hours < 24) return `${hours} sa`;
  const days = Math.round(hours / 24);
  return `${days} g`;
}

export function NotificationArea() {
  const { notifications: fallback } = useDashboard();
  const router = useRouter();
  const [alerts, setAlerts] = useState<DashboardAlert[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [markingAll, setMarkingAll] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    const result = await fetchDashboardAlerts({ limit: 8 });
    if (!result.ok) return;
    const { alerts: list, unreadCount: unread } = normalizeAlertsPayload(result.data);
    setAlerts(list);
    setUnreadCount(unread);
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 60_000);
    return () => window.clearInterval(id);
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const items =
    alerts.length > 0
      ? alerts
      : fallback.map((n) => ({
          id: Number(n.id) || 0,
          title: n.title,
          body: "",
          severity: "INFO",
          notification_type: "",
          category: "",
          entity_type: "",
          entity_id: "",
          href: "",
          is_read: n.read,
          created_at: "",
        }));

  const displayUnread =
    alerts.length > 0 ? unreadCount : items.filter((n) => !n.is_read).length;

  async function onOpenAlert(alert: DashboardAlert) {
    if (!alert.is_read && alert.id) {
      void markAlertRead(alert.id).then((res) => {
        if (res.ok) {
          setAlerts((prev) =>
            prev.map((a) => (a.id === alert.id ? { ...a, is_read: true } : a)),
          );
          setUnreadCount((c) => Math.max(0, c - 1));
        }
      });
    }
    setOpen(false);
    if (alert.href) {
      router.push(alert.href);
    }
  }

  async function onMarkAll() {
    setMarkingAll(true);
    const res = await markAllAlertsRead();
    setMarkingAll(false);
    if (res.ok) {
      setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })));
      setUnreadCount(0);
    }
  }

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="relative rounded-lg p-2 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
        aria-label="Bildirimler"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
      >
        <svg
          viewBox="0 0 24 24"
          className="size-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
        >
          <path
            d="M18 8A6 6 0 106 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        {displayUnread > 0 ? (
          <span className="bg-brand absolute top-1.5 right-1.5 size-2 rounded-full ring-2 ring-white" />
        ) : null}
      </button>

      {open ? (
        <div
          id={panelId}
          role="menu"
          className="absolute right-0 z-30 mt-2 w-96 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
        >
          <div className="flex items-start justify-between gap-2 border-b border-slate-100 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">Bildirimler</p>
              <p className="text-xs text-slate-500">
                {displayUnread > 0 ? `${displayUnread} okunmamış` : "Hepsi okundu"}
              </p>
            </div>
            {displayUnread > 0 ? (
              <button
                type="button"
                disabled={markingAll}
                onClick={() => void onMarkAll()}
                className="text-brand shrink-0 text-xs font-medium hover:underline disabled:opacity-50"
              >
                Tümünü okundu yap
              </button>
            ) : null}
          </div>
          <ul className="max-h-80 overflow-y-auto py-1">
            {items.length === 0 ? (
              <li className="px-4 py-6 text-center text-sm text-slate-500">Bildirim yok</li>
            ) : (
              items.map((item) => (
                <li key={item.id || item.title}>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => void onOpenAlert(item)}
                    className={[
                      "w-full border-b border-slate-50 px-4 py-3 text-left last:border-0",
                      item.is_read ? "text-slate-500" : "bg-brand/5 text-slate-800",
                    ].join(" ")}
                  >
                    <span className="block text-sm font-medium">{item.title}</span>
                    {item.body ? (
                      <span className="mt-0.5 line-clamp-2 block text-xs text-slate-500">
                        {item.body}
                      </span>
                    ) : null}
                    {item.created_at ? (
                      <span className="mt-1 block text-[11px] text-slate-400">
                        {formatRelative(item.created_at)}
                      </span>
                    ) : null}
                  </button>
                </li>
              ))
            )}
          </ul>
          <div className="border-t border-slate-100 px-4 py-2.5">
            <Link
              href="/notifications"
              onClick={() => setOpen(false)}
              className="text-brand block text-center text-sm font-medium hover:underline"
            >
              Tüm bildirimler
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
