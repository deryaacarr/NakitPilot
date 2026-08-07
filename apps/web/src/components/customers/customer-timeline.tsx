"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { fetchCustomerTimeline } from "@/lib/collections/api";
import type { TimelineEvent } from "@/lib/collections/types";
import { formatDate } from "@/lib/customers/format";

export function CustomerTimeline({ customerId }: { customerId: number }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void fetchCustomerTimeline(customerId).then((result) => {
      if (cancelled) return;
      setLoading(false);
      if (result.ok) setEvents(result.data.results);
    });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  if (loading) return <LoadingSkeleton lines={5} />;
  if (events.length === 0) {
    return <EmptyState title="Aktivite yok" description="Henüz tahsilat kaydı bulunmuyor." />;
  }

  return (
    <ol className="space-y-3">
      {events.map((event) => (
        <li key={event.id} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-sm font-semibold text-slate-900">{event.label}</p>
            <time className="text-xs text-slate-500">
              {formatDate(event.occurred_at.slice(0, 10))}
            </time>
          </div>
          <p className="mt-1 text-sm text-slate-700">{event.summary}</p>
          {event.notes ? <p className="mt-1 text-xs text-slate-500">{event.notes}</p> : null}
          {event.actor ? <p className="mt-1 text-xs text-slate-400">{event.actor}</p> : null}
        </li>
      ))}
    </ol>
  );
}
