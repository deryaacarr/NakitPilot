"use client";

import { useCallback, useEffect, useState } from "react";

import { CompleteTaskModal } from "@/components/collections/complete-task-modal";
import { PrepareCallModal } from "@/components/collections/prepare-call-modal";
import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { fetchTodayBoard } from "@/lib/collections/api";
import {
  TASK_TYPE_LABELS,
  type CollectionTask,
  type TodayBoard,
} from "@/lib/collections/types";
import { formatDate, formatMoney } from "@/lib/customers/format";
import type { AppError } from "@/lib/errors";

const GROUPS: { key: keyof TodayBoard; title: string }[] = [
  { key: "overdue", title: "Gecikmiş görevler" },
  { key: "today", title: "Bugünün görevleri" },
  { key: "upcoming", title: "Yaklaşan görevler" },
  { key: "completed", title: "Tamamlanan görevler" },
];

function priorityTone(priority: string) {
  if (priority === "CRITICAL" || priority === "HIGH") return "danger" as const;
  if (priority === "MEDIUM") return "warning" as const;
  return "neutral" as const;
}

export function CollectionsBoard() {
  const { toast } = useToast();
  const [board, setBoard] = useState<TodayBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [active, setActive] = useState<CollectionTask | null>(null);
  const [prepTask, setPrepTask] = useState<CollectionTask | null>(null);

  const load = useCallback(async () => {
    const result = await fetchTodayBoard();
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      setBoard(null);
      return;
    }
    setError(null);
    setBoard(result.data);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingSkeleton lines={10} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!board) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Tahsilat</h1>
        <p className="mt-1 text-sm text-slate-600">Bugünün görev panosu</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {GROUPS.map((group) => (
          <section key={group.key} className="rounded-xl border border-slate-200 bg-white">
            <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-900">{group.title}</h2>
              <span className="text-xs text-slate-500">{board[group.key].length}</span>
            </header>
            <div className="max-h-[28rem] space-y-3 overflow-y-auto p-3">
              {board[group.key].length === 0 ? (
                <EmptyState title="Kayıt yok" description="Bu grupta görev bulunmuyor." />
              ) : (
                board[group.key].map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    onPrepare={
                      task.status === "COMPLETED" || task.status === "CANCELLED"
                        ? undefined
                        : () => setPrepTask(task)
                    }
                    onComplete={
                      task.status === "COMPLETED" || task.status === "CANCELLED"
                        ? undefined
                        : () => setActive(task)
                    }
                  />
                ))
              )}
            </div>
          </section>
        ))}
      </div>

      {active ? (
        <CompleteTaskModal
          task={active}
          onClose={() => setActive(null)}
          onDone={() => {
            setActive(null);
            toast({ title: "Görev tamamlandı", tone: "success" });
            void load();
          }}
        />
      ) : null}

      {prepTask ? (
        <PrepareCallModal
          taskId={prepTask.id}
          customerName={prepTask.customer_name}
          onClose={() => setPrepTask(null)}
        />
      ) : null}
    </div>
  );
}

function TaskCard({
  task,
  onComplete,
  onPrepare,
}: {
  task: CollectionTask;
  onComplete?: () => void;
  onPrepare?: () => void;
}) {
  return (
    <article className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">{task.customer_name}</p>
          <p className="text-xs text-slate-500">{task.title}</p>
        </div>
        <Badge tone={priorityTone(task.priority)}>{task.priority}</Badge>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600 sm:grid-cols-3">
        <div>
          <dt className="text-slate-400">Tutar</dt>
          <dd className="font-medium text-slate-800">{formatMoney(task.overdue_balance)}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Gecikme</dt>
          <dd className="font-medium text-slate-800">
            {task.overdue_days != null ? `${task.overdue_days} gün` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Risk</dt>
          <dd className="font-medium text-slate-800">{task.customer_risk_status}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Tip</dt>
          <dd className="font-medium text-slate-800">
            {TASK_TYPE_LABELS[task.task_type] ?? task.task_type}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Sorumlu</dt>
          <dd className="font-medium text-slate-800">
            {task.assigned_to_name || task.assigned_to_email || "—"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Son görüşme</dt>
          <dd className="font-medium text-slate-800">
            {task.last_contact_at ? formatDate(task.last_contact_at.slice(0, 10)) : "—"}
          </dd>
        </div>
        <div className="col-span-2 sm:col-span-3">
          <dt className="text-slate-400">Ödeme sözü</dt>
          <dd className="font-medium text-slate-800">
            {task.payment_promise
              ? `${formatMoney(task.payment_promise.amount)} · ${formatDate(task.payment_promise.promised_date)} (${task.payment_promise.status})`
              : "—"}
          </dd>
        </div>
      </dl>
      {onComplete || onPrepare ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {onPrepare ? (
            <Button type="button" size="sm" variant="outline" onClick={onPrepare}>
              Aramadan önce hazırla
            </Button>
          ) : null}
          {onComplete ? (
            <Button type="button" size="sm" onClick={onComplete}>
              Tamamla
            </Button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
