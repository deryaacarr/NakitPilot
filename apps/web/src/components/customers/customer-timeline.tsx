"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { fetchCustomerTimeline } from "@/lib/collections/api";
import type { TimelineEvent } from "@/lib/collections/types";
import { cn } from "@/lib/cn";

const KIND_FILTERS: { id: string; label: string; kinds: string[] }[] = [
  { id: "all", label: "Tümü", kinds: [] },
  { id: "CALL", label: "Telefon", kinds: ["CALL"] },
  { id: "EMAIL", label: "E-posta", kinds: ["EMAIL"] },
  { id: "WHATSAPP", label: "WhatsApp", kinds: ["WHATSAPP"] },
  { id: "PAYMENT", label: "Ödeme", kinds: ["PAYMENT"] },
  { id: "TASK", label: "Görev", kinds: ["TASK", "TASK_COMPLETED"] },
  { id: "NOTE", label: "Not", kinds: ["NOTE"] },
  { id: "PROMISE", label: "Ödeme sözü", kinds: ["PROMISE"] },
  { id: "DISPUTE", label: "İtiraz", kinds: ["DISPUTE"] },
  { id: "RISK_CHANGE", label: "Risk", kinds: ["RISK_CHANGE"] },
];

const KIND_ICON: Record<string, string> = {
  CALL: "☎",
  EMAIL: "✉",
  WHATSAPP: "💬",
  PAYMENT: "₺",
  TASK: "☑",
  TASK_COMPLETED: "✓",
  NOTE: "✎",
  PROMISE: "◷",
  DISPUTE: "⚠",
  RISK_CHANGE: "◇",
  OTHER: "•",
};

export function CustomerTimeline({
  customerId,
  refreshKey = 0,
}: {
  customerId: number;
  refreshKey?: number;
}) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterId, setFilterId] = useState("all");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const activeKinds = useMemo(
    () => KIND_FILTERS.find((f) => f.id === filterId)?.kinds || [],
    [filterId],
  );

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchCustomerTimeline(
      customerId,
      activeKinds.length ? activeKinds : undefined,
    );
    setLoading(false);
    if (result.ok) setEvents(result.data.results);
    else setEvents([]);
  }, [customerId, activeKinds]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {KIND_FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilterId(f.id)}
            className={cn(
              "rounded-full border px-2.5 py-1 text-xs font-medium",
              filterId === f.id
                ? "border-primary bg-primary/10 text-primary"
                : "border-border-default text-muted hover:bg-surface-tertiary",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? <LoadingSkeleton lines={5} /> : null}
      {!loading && events.length === 0 ? (
        <EmptyState title="Aktivite yok" description="Bu filtrede kayıt bulunmuyor." />
      ) : null}

      {!loading && events.length > 0 ? (
        <ol className="relative space-y-0 border-l border-border-default pl-4">
          {events.map((event) => {
            const long = (event.notes || "").length > 140;
            const open = expanded[event.id];
            const notes =
              long && !open ? `${event.notes.slice(0, 140).trim()}…` : event.notes;
            return (
              <li key={event.id} className="relative pb-4">
                <span
                  className="absolute top-0 -left-[1.4rem] flex size-7 items-center justify-center rounded-full border border-border-default bg-surface-primary text-xs"
                  aria-hidden
                >
                  {KIND_ICON[event.kind] || KIND_ICON.OTHER}
                </span>
                <div className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary px-4 py-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="text-sm font-semibold text-foreground">
                      {event.label}
                      <span className="ml-2 text-xs font-normal text-muted">{event.summary}</span>
                    </p>
                    <time className="text-xs text-muted" dateTime={event.occurred_at}>
                      {formatDateTime(event.occurred_at)}
                    </time>
                  </div>
                  {notes ? (
                    <p className="mt-1 whitespace-pre-wrap text-sm text-muted">{notes}</p>
                  ) : null}
                  {long ? (
                    <button
                      type="button"
                      className="mt-1 text-xs font-semibold text-primary"
                      onClick={() =>
                        setExpanded((prev) => ({ ...prev, [event.id]: !prev[event.id] }))
                      }
                    >
                      {open ? "Daralt" : "Devamını oku"}
                    </button>
                  ) : null}
                  {event.actor ? (
                    <p className="mt-1.5 text-xs text-subtle">Yapan: {event.actor}</p>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      ) : null}
    </div>
  );
}

function formatDateTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.replace("T", " ").slice(0, 16);
  return d.toLocaleString("tr-TR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
