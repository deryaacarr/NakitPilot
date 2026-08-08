"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { listCollectionTasks } from "@/lib/collections/api";
import type { CollectionTask } from "@/lib/collections/types";

function localDayKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function dayKey(iso: string) {
  return iso.slice(0, 10);
}

export function CollectionCalendar() {
  const [tasks, setTasks] = useState<CollectionTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const res = await listCollectionTasks({ page_size: 200 });
      if (cancelled) return;
      setLoading(false);
      if (res.ok) setTasks(res.data.results || []);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const byDay = useMemo(() => {
    const map = new Map<string, CollectionTask[]>();
    for (const t of tasks) {
      const key = dayKey(t.due_date);
      const list = map.get(key) || [];
      list.push(t);
      map.set(key, list);
    }
    return map;
  }, [tasks]);

  const days = useMemo(() => {
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    const firstDow = new Date(year, month, 1).getDay(); // 0 Sun
    const startOffset = (firstDow + 6) % 7; // Monday-first
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const cells: Array<{ date: Date | null; key: string }> = [];
    for (let i = 0; i < startOffset; i++) cells.push({ date: null, key: `e-${i}` });
    for (let d = 1; d <= daysInMonth; d++) {
      const date = new Date(year, month, d);
      cells.push({ date, key: localDayKey(date) });
    }
    return cells;
  }, [cursor]);

  const title = cursor.toLocaleDateString("tr-TR", { month: "long", year: "numeric" });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl tracking-tight text-foreground">Tahsilat takvimi</h1>
          <p className="mt-1 text-sm text-muted">Görev vadelerine göre aylık görünüm</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded-[var(--radius-md)] border border-border-default px-3 py-1.5 text-sm"
            onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}
          >
            ←
          </button>
          <span className="min-w-[10rem] text-center text-sm font-semibold capitalize">{title}</span>
          <button
            type="button"
            className="rounded-[var(--radius-md)] border border-border-default px-3 py-1.5 text-sm"
            onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
          >
            →
          </button>
        </div>
      </div>

      {loading ? (
        <LoadingSkeleton className="h-64" />
      ) : (
        <div className="grid grid-cols-7 gap-px overflow-hidden rounded-[var(--radius-lg)] border border-border-default bg-border-default">
          {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((d) => (
            <div key={d} className="bg-surface-secondary px-2 py-2 text-center text-xs font-semibold text-subtle">
              {d}
            </div>
          ))}
          {days.map((cell) => {
            if (!cell.date) {
              return <div key={cell.key} className="min-h-[5.5rem] bg-surface-tertiary/40" />;
            }
            const key = localDayKey(cell.date);
            const dayTasks = byDay.get(key) || [];
            return (
              <div key={cell.key} className="min-h-[5.5rem] bg-surface-primary p-2">
                <p className="text-xs font-semibold text-muted">{cell.date.getDate()}</p>
                <ul className="mt-1 space-y-1">
                  {dayTasks.slice(0, 3).map((t) => (
                    <li key={t.id}>
                      <Link
                        href={`/customers/${t.customer}`}
                        className="block truncate rounded bg-primary/10 px-1.5 py-0.5 text-[11px] text-primary"
                        title={t.title}
                      >
                        {t.customer_name}
                      </Link>
                    </li>
                  ))}
                  {dayTasks.length > 3 ? (
                    <li className="text-[10px] text-subtle">+{dayTasks.length - 3}</li>
                  ) : null}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
