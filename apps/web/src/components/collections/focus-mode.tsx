"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CompleteTaskModal } from "@/components/collections/complete-task-modal";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { fetchPrepareCall, type CallPrepPayload } from "@/lib/collections/api";
import type { CollectionTask, TodayBoard } from "@/lib/collections/types";
import { formatDate, formatMoney } from "@/lib/customers/format";

function buildQueue(board: TodayBoard): CollectionTask[] {
  return [...board.overdue, ...board.today, ...board.upcoming].filter(
    (t) => t.status === "OPEN" || t.status === "IN_PROGRESS",
  );
}

export function FocusMode({
  board,
  onExit,
  onCompleted,
}: {
  board: TodayBoard;
  onExit: () => void;
  onCompleted: () => void;
}) {
  const { toast } = useToast();
  const queue = useMemo(() => buildQueue(board), [board]);
  const [index, setIndex] = useState(0);
  const [prep, setPrep] = useState<CallPrepPayload | null>(null);
  const [prepError, setPrepError] = useState<string | null>(null);
  const [prepLoading, setPrepLoading] = useState(false);
  const [completeOpen, setCompleteOpen] = useState(false);

  const task = queue[index] ?? null;
  const remaining = Math.max(queue.length - index, 0);

  const loadPrep = useCallback(async (taskId: number) => {
    setPrepLoading(true);
    setPrep(null);
    setPrepError(null);
    const res = await fetchPrepareCall(taskId);
    setPrepLoading(false);
    if (!res.ok) {
      setPrepError(res.error.message);
      return;
    }
    setPrep(res.data);
  }, []);

  useEffect(() => {
    if (!task) return;
    void loadPrep(task.id);
  }, [task, loadPrep]);

  useEffect(() => {
    if (index >= queue.length && queue.length > 0) {
      setIndex(0);
    }
  }, [queue.length, index]);

  if (!task) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-serif text-2xl tracking-tight">Odak modu</h2>
          <Button type="button" variant="outline" onClick={onExit}>
            Çık
          </Button>
        </div>
        <EmptyState
          title="Sırada görev yok"
          description="Gecikmiş, bugün ve yaklaşan açık görevler bitti."
        />
      </div>
    );
  }

  const lastNote = prep?.previous_call_notes?.[0] ?? null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-subtle">Odak modu</p>
          <h2 className="font-serif text-2xl tracking-tight text-foreground">
            Sıradaki müşteri
          </h2>
          <p className="text-sm text-muted">
            {index + 1} / {queue.length} · kalan {remaining}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={index <= 0}
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
          >
            Önceki
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={index >= queue.length - 1}
            onClick={() => setIndex((i) => Math.min(queue.length - 1, i + 1))}
          >
            Atla
          </Button>
          <Button type="button" variant="outline" onClick={onExit}>
            Çık
          </Button>
          <Button type="button" onClick={() => setCompleteOpen(true)}>
            Tamamla
          </Button>
        </div>
      </div>

      <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-serif text-3xl tracking-tight text-foreground">
              {task.customer_name}
            </h3>
            <p className="mt-1 text-sm text-muted">{task.title}</p>
          </div>
          <Link
            href={`/customers/${task.customer}`}
            className="text-sm font-semibold text-brand hover:underline"
          >
            Müşteri kartı →
          </Link>
        </div>
        <dl className="mt-4 grid gap-3 sm:grid-cols-3">
          <div>
            <dt className="text-xs text-subtle">Açık bakiye</dt>
            <dd className="font-semibold">
              {formatMoney(task.open_balance ?? task.overdue_balance)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-subtle">Gecikme</dt>
            <dd className="font-semibold">
              {task.overdue_days != null ? `${task.overdue_days} gün` : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-subtle">Telefon</dt>
            <dd className="font-semibold">
              {task.customer_phone ? (
                <a href={`tel:${task.customer_phone.replace(/\s/g, "")}`} className="text-brand">
                  {task.customer_phone}
                </a>
              ) : (
                "—"
              )}
            </dd>
          </div>
        </dl>
      </section>

      {prepLoading ? <LoadingSkeleton lines={6} /> : null}
      {prepError ? <p className="text-sm text-danger">{prepError}</p> : null}

      {prep ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
            <h4 className="text-sm font-semibold">Arama özeti</h4>
            <p className="mt-2 text-sm text-muted">
              Açık bakiye {formatMoney(prep.open_balance)}
              {prep.last_payment_promise
                ? ` · Son söz ${formatMoney(prep.last_payment_promise.amount)} (${formatDate(prep.last_payment_promise.promised_date)})`
                : ""}
            </p>
            <h5 className="mt-4 text-xs font-semibold uppercase tracking-wide text-subtle">
              Önerilen konuşma noktaları
            </h5>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-foreground">
              {prep.talking_points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </section>

          <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
            <h4 className="text-sm font-semibold">Açık faturalar</h4>
            {prep.open_invoices.length === 0 ? (
              <p className="mt-2 text-sm text-muted">Açık fatura yok.</p>
            ) : (
              <ul className="mt-2 space-y-2 text-sm">
                {prep.open_invoices.map((inv) => (
                  <li key={inv.id} className="flex justify-between gap-2 border-b border-border-default/60 pb-2">
                    <span>
                      {inv.number}
                      <span className="text-muted">
                        {" "}
                        · {inv.overdue_days > 0 ? `${inv.overdue_days}g gecikme` : "vadesi gelmemiş"}
                      </span>
                    </span>
                    <span className="font-medium tabular-nums">
                      {formatMoney(inv.remaining_amount)}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            <h5 className="mt-4 text-xs font-semibold uppercase tracking-wide text-subtle">
              Son görüşme
            </h5>
            {lastNote ? (
              <p className="mt-2 text-sm text-foreground">
                <span className="text-muted">
                  {formatDate(lastNote.occurred_at.slice(0, 10))} ·{" "}
                </span>
                {lastNote.summary || lastNote.notes || "—"}
              </p>
            ) : (
              <p className="mt-2 text-sm text-muted">Önceki görüşme kaydı yok.</p>
            )}
          </section>
        </div>
      ) : null}

      {completeOpen ? (
        <CompleteTaskModal
          task={task}
          onClose={() => setCompleteOpen(false)}
          onDone={() => {
            setCompleteOpen(false);
            toast({ title: "Görev tamamlandı — sıradaki", tone: "success" });
            // Keep index; completed task drops out of queue after refresh.
            onCompleted();
          }}
        />
      ) : null}
    </div>
  );
}
