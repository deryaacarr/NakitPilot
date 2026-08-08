"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { PromiseCalendarView } from "@/components/promises/promise-calendar-view";
import { PromiseCreateForm } from "@/components/promises/promise-create-form";
import { PromiseStatusCards } from "@/components/promises/promise-status-cards";
import { ErrorState } from "@/components/errors";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { cn } from "@/lib/cn";
import type { AppError } from "@/lib/errors";
import { fetchPromiseStatusBoard, listPaymentPromises } from "@/lib/promises/api";
import type { PaymentPromise, PromiseStatusBoard } from "@/lib/promises/types";

type Tab = "cards" | "calendar";

export function PromiseExperience() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("cards");
  const [board, setBoard] = useState<PromiseStatusBoard | null>(null);
  const [calendarPromises, setCalendarPromises] = useState<PaymentPromise[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [formKey, setFormKey] = useState(0);

  const load = useCallback(async () => {
    const [boardRes, listRes] = await Promise.all([
      fetchPromiseStatusBoard(),
      listPaymentPromises({ page_size: 200 }),
    ]);
    setLoading(false);
    if (!boardRes.ok) {
      setError(boardRes.error);
      setBoard(null);
      return;
    }
    setError(null);
    setBoard(boardRes.data);
    if (listRes.ok) setCalendarPromises(listRes.data.results || []);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingSkeleton lines={10} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!board) return null;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl tracking-tight text-foreground">Ödeme sözleri</h1>
          <p className="mt-1 text-sm text-muted">Durum kartları ve takvim deneyimi</p>
        </div>
        <div className="inline-flex rounded-[var(--radius-md)] border border-border-default p-0.5">
          {(
            [
              ["cards", "Durum kartları"],
              ["calendar", "Takvim"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={cn(
                "rounded-[calc(var(--radius-md)-2px)] px-3 py-1.5 text-xs font-semibold",
                tab === id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <PromiseCreateForm
        key={formKey}
        onCreated={() => {
          setFormKey((k) => k + 1);
          void load();
        }}
      />

      {tab === "cards" ? <PromiseStatusCards board={board} /> : null}
      {tab === "calendar" ? (
        <PromiseCalendarView
          promises={calendarPromises}
          onCreateForDate={(date) => {
            router.replace(`/promises?create=1&date=${date}`);
            setFormKey((k) => k + 1);
          }}
        />
      ) : null}
    </div>
  );
}
