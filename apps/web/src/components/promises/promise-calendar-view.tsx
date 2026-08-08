"use client";

import { useMemo, useState } from "react";

import { PromiseStatusCard } from "@/components/promises/promise-status-cards";
import { Button } from "@/components/ui/button";
import { Drawer } from "@/components/ui/drawer";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/cn";
import { formatDate, formatMoney } from "@/lib/customers/format";
import type { PaymentPromise } from "@/lib/promises/types";

type CalMode = "day" | "week" | "month";

function localDayKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addDays(d: Date, n: number) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function startOfWeek(d: Date) {
  const x = new Date(d);
  const dow = (x.getDay() + 6) % 7;
  x.setDate(x.getDate() - dow);
  x.setHours(0, 0, 0, 0);
  return x;
}

/** Calendar color by status / timing (NP-432). */
export function promiseCalendarColor(promise: PaymentPromise, todayKey: string): string {
  if (promise.status === "FULFILLED") return "#059669"; // green
  if (promise.status === "BROKEN") return "#dc2626"; // red
  const day = promise.promised_date.slice(0, 10);
  if (day === todayKey) return "#ea580c"; // orange
  return "#2563eb"; // blue upcoming / pending
}

export function PromiseCalendarView({
  promises,
  onCreateForDate,
}: {
  promises: PaymentPromise[];
  onCreateForDate: (date: string) => void;
}) {
  const [mode, setMode] = useState<CalMode>("month");
  const [cursor, setCursor] = useState(() => new Date());
  const [drawerDate, setDrawerDate] = useState<string | null>(null);
  const todayKey = localDayKey(new Date());

  const byDay = useMemo(() => {
    const map = new Map<string, PaymentPromise[]>();
    for (const p of promises) {
      const key = p.promised_date.slice(0, 10);
      const list = map.get(key) || [];
      list.push(p);
      map.set(key, list);
    }
    return map;
  }, [promises]);

  const drawerItems = drawerDate ? byDay.get(drawerDate) || [] : [];

  const title = useMemo(() => {
    if (mode === "month") {
      return cursor.toLocaleDateString("tr-TR", { month: "long", year: "numeric" });
    }
    if (mode === "week") {
      const start = startOfWeek(cursor);
      const end = addDays(start, 6);
      return `${formatDate(localDayKey(start))} – ${formatDate(localDayKey(end))}`;
    }
    return formatDate(localDayKey(cursor));
  }, [cursor, mode]);

  function shift(dir: -1 | 1) {
    if (mode === "month") {
      setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + dir, 1));
    } else if (mode === "week") {
      setCursor(addDays(cursor, dir * 7));
    } else {
      setCursor(addDays(cursor, dir));
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex rounded-[var(--radius-md)] border border-border-default p-0.5">
          {(
            [
              ["day", "Gün"],
              ["week", "Hafta"],
              ["month", "Ay"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setMode(id)}
              className={cn(
                "rounded-[calc(var(--radius-md)-2px)] px-3 py-1.5 text-xs font-semibold",
                mode === id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded-[var(--radius-md)] border border-border-default px-3 py-1.5 text-sm"
            onClick={() => shift(-1)}
          >
            ←
          </button>
          <span className="min-w-[10rem] text-center text-sm font-semibold capitalize">{title}</span>
          <button
            type="button"
            className="rounded-[var(--radius-md)] border border-border-default px-3 py-1.5 text-sm"
            onClick={() => shift(1)}
          >
            →
          </button>
        </div>
        <div className="flex flex-wrap gap-3 text-[11px] text-muted">
          <Legend color="#059669" label="Karşılandı" />
          <Legend color="#ea580c" label="Bugün" />
          <Legend color="#dc2626" label="Bozuldu" />
          <Legend color="#2563eb" label="Yaklaşan" />
        </div>
      </div>

      {mode === "month" ? (
        <MonthGrid
          cursor={cursor}
          byDay={byDay}
          todayKey={todayKey}
          onDayClick={setDrawerDate}
        />
      ) : null}
      {mode === "week" ? (
        <WeekGrid
          cursor={cursor}
          byDay={byDay}
          todayKey={todayKey}
          onDayClick={setDrawerDate}
        />
      ) : null}
      {mode === "day" ? (
        <DayPanel
          cursor={cursor}
          items={byDay.get(localDayKey(cursor)) || []}
          todayKey={todayKey}
          onOpenDrawer={() => setDrawerDate(localDayKey(cursor))}
          onCreate={() => onCreateForDate(localDayKey(cursor))}
        />
      ) : null}

      <Drawer
        open={Boolean(drawerDate)}
        onClose={() => setDrawerDate(null)}
        title={drawerDate ? formatDate(drawerDate) : "Sözler"}
        footer={
          drawerDate ? (
            <Button
              type="button"
              onClick={() => {
                onCreateForDate(drawerDate);
                setDrawerDate(null);
              }}
            >
              Bu güne söz ekle
            </Button>
          ) : null
        }
      >
        {drawerItems.length === 0 ? (
          <EmptyState title="Söz yok" description="Bu günde ödeme sözü bulunmuyor." />
        ) : (
          <div className="space-y-2">
            {drawerItems.map((p) => (
              <PromiseStatusCard key={p.id} promise={p} />
            ))}
          </div>
        )}
      </Drawer>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="size-2.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function MonthGrid({
  cursor,
  byDay,
  todayKey,
  onDayClick,
}: {
  cursor: Date;
  byDay: Map<string, PaymentPromise[]>;
  todayKey: string;
  onDayClick: (key: string) => void;
}) {
  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const firstDow = new Date(year, month, 1).getDay();
  const startOffset = (firstDow + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: Array<{ date: Date | null; key: string }> = [];
  for (let i = 0; i < startOffset; i++) cells.push({ date: null, key: `e-${i}` });
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(year, month, d);
    cells.push({ date, key: localDayKey(date) });
  }

  return (
    <div className="grid grid-cols-7 gap-px overflow-hidden rounded-[var(--radius-lg)] border border-border-default bg-border-default">
      {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((d) => (
        <div
          key={d}
          className="bg-surface-secondary px-2 py-2 text-center text-xs font-semibold text-subtle"
        >
          {d}
        </div>
      ))}
      {cells.map((cell) => {
        const items = cell.date ? byDay.get(cell.key) || [] : [];
        return (
          <button
            key={cell.key}
            type="button"
            disabled={!cell.date}
            onClick={() => cell.date && onDayClick(cell.key)}
            className={cn(
              "min-h-[5.5rem] bg-surface-primary p-1.5 text-left",
              cell.key === todayKey && "ring-1 ring-inset ring-brand/40",
              cell.date && "hover:bg-surface-secondary/60",
            )}
          >
            {cell.date ? (
              <>
                <p className="text-[11px] font-semibold text-muted">{cell.date.getDate()}</p>
                <ul className="mt-1 space-y-0.5">
                  {items.slice(0, 3).map((p) => (
                    <li
                      key={p.id}
                      className="truncate rounded px-1 py-0.5 text-[10px] font-medium text-white"
                      style={{ background: promiseCalendarColor(p, todayKey) }}
                      title={`${p.customer_name} · ${formatMoney(p.amount, p.currency)}`}
                    >
                      {p.customer_name}
                    </li>
                  ))}
                  {items.length > 3 ? (
                    <li className="px-1 text-[10px] text-muted">+{items.length - 3}</li>
                  ) : null}
                </ul>
              </>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

function WeekGrid({
  cursor,
  byDay,
  todayKey,
  onDayClick,
}: {
  cursor: Date;
  byDay: Map<string, PaymentPromise[]>;
  todayKey: string;
  onDayClick: (key: string) => void;
}) {
  const start = startOfWeek(cursor);
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));

  return (
    <div className="grid gap-2 md:grid-cols-7">
      {days.map((date) => {
        const key = localDayKey(date);
        const items = byDay.get(key) || [];
        return (
          <button
            key={key}
            type="button"
            onClick={() => onDayClick(key)}
            className={cn(
              "min-h-[10rem] rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-2 text-left",
              key === todayKey && "ring-1 ring-brand/40",
            )}
          >
            <p className="text-xs font-semibold capitalize text-muted">
              {date.toLocaleDateString("tr-TR", { weekday: "short", day: "numeric" })}
            </p>
            <ul className="mt-2 space-y-1">
              {items.map((p) => (
                <li
                  key={p.id}
                  className="rounded px-1.5 py-1 text-[11px] font-medium text-white"
                  style={{ background: promiseCalendarColor(p, todayKey) }}
                >
                  {p.customer_name}
                  <span className="mt-0.5 block opacity-90">
                    {formatMoney(p.amount, p.currency)}
                  </span>
                </li>
              ))}
            </ul>
          </button>
        );
      })}
    </div>
  );
}

function DayPanel({
  cursor,
  items,
  todayKey,
  onOpenDrawer,
  onCreate,
}: {
  cursor: Date;
  items: PaymentPromise[];
  todayKey: string;
  onOpenDrawer: () => void;
  onCreate: () => void;
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold capitalize">
          {cursor.toLocaleDateString("tr-TR", {
            weekday: "long",
            day: "numeric",
            month: "long",
          })}
        </h3>
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onOpenDrawer}>
            Drawer’da aç
          </Button>
          <Button type="button" size="sm" onClick={onCreate}>
            Söz ekle
          </Button>
        </div>
      </div>
      {items.length === 0 ? (
        <EmptyState title="Söz yok" description="Bu günde ödeme sözü yok." />
      ) : (
        <ul className="space-y-2">
          {items.map((p) => (
            <li
              key={p.id}
              className="flex items-center justify-between gap-2 rounded-[var(--radius-md)] border border-border-default px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <span
                  className="size-2.5 rounded-full"
                  style={{ background: promiseCalendarColor(p, todayKey) }}
                />
                <div>
                  <p className="text-sm font-semibold">{p.customer_name}</p>
                  <p className="text-xs text-muted">{p.status}</p>
                </div>
              </div>
              <p className="text-sm font-medium">{formatMoney(p.amount, p.currency)}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
