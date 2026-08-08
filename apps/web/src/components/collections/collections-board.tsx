"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AssignTaskModal, PostponeTaskModal } from "@/components/collections/task-action-modals";
import { CompleteTaskModal } from "@/components/collections/complete-task-modal";
import { DaySummaryPanel } from "@/components/collections/day-summary-panel";
import { FocusMode } from "@/components/collections/focus-mode";
import { PrepareCallModal } from "@/components/collections/prepare-call-modal";
import { TaskCard } from "@/components/collections/task-card";
import { ErrorState } from "@/components/errors";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";
import { fetchTodayBoard, updateCollectionTask } from "@/lib/collections/api";
import {
  type BoardGroupKey,
  type CollectionTask,
  type TodayBoard,
  type WorkViewMode,
} from "@/lib/collections/types";
import type { AppError } from "@/lib/errors";

const GROUPS: { key: BoardGroupKey; title: string }[] = [
  { key: "overdue", title: "Gecikmiş" },
  { key: "today", title: "Bugün" },
  { key: "upcoming", title: "Yaklaşan" },
  { key: "completed", title: "Tamamlanan" },
];

const VIEW_MODES: { id: WorkViewMode; label: string }[] = [
  { id: "kanban", label: "Kanban" },
  { id: "list", label: "Liste" },
  { id: "calendar", label: "Takvim" },
];

function localDayKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function CollectionsBoard() {
  const { toast } = useToast();
  const [board, setBoard] = useState<TodayBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [view, setView] = useState<WorkViewMode>("kanban");
  const [focus, setFocus] = useState(false);
  const [summaryKey, setSummaryKey] = useState(0);

  const [active, setActive] = useState<CollectionTask | null>(null);
  const [prepTask, setPrepTask] = useState<CollectionTask | null>(null);
  const [postponeTask, setPostponeTask] = useState<CollectionTask | null>(null);
  const [assignTask, setAssignTask] = useState<CollectionTask | null>(null);

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

  const refresh = useCallback(async () => {
    await load();
    setSummaryKey((k) => k + 1);
  }, [load]);

  const allTasks = useMemo(() => {
    if (!board) return [] as CollectionTask[];
    return [...board.overdue, ...board.today, ...board.upcoming, ...board.completed];
  }, [board]);

  const openCount = useMemo(() => {
    if (!board) return 0;
    return board.overdue.length + board.today.length + board.upcoming.length;
  }, [board]);

  async function startTask(task: CollectionTask) {
    const res = await updateCollectionTask(task.id, { status: "IN_PROGRESS" });
    if (!res.ok) {
      toast({ title: "Başlatılamadı", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Görev başlatıldı", tone: "success" });
    void refresh();
  }

  function actionsFor(task: CollectionTask) {
    if (task.status === "COMPLETED" || task.status === "CANCELLED") return undefined;
    return {
      onStart: () => void startTask(task),
      onComplete: () => setActive(task),
      onPostpone: () => setPostponeTask(task),
      onAssign: () => setAssignTask(task),
      onPrepare: () => setPrepTask(task),
    };
  }

  if (loading) return <LoadingSkeleton lines={10} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!board) return null;

  if (focus) {
    return (
      <FocusMode
        board={board}
        onExit={() => setFocus(false)}
        onCompleted={() => void refresh()}
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="font-serif text-3xl tracking-tight text-foreground">
            Günlük çalışma
          </h1>
          <p className="mt-1 text-sm text-muted">
            Operasyon ekranı · {openCount} açık görev
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-[var(--radius-md)] border border-border-default p-0.5">
            {VIEW_MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setView(m.id)}
                className={cn(
                  "rounded-[calc(var(--radius-md)-2px)] px-3 py-1.5 text-xs font-semibold",
                  view === m.id
                    ? "bg-primary text-primary-foreground"
                    : "text-muted hover:text-foreground",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
          <Button type="button" onClick={() => setFocus(true)} disabled={openCount === 0}>
            Odak modu
          </Button>
          <Link
            href="/collections/field"
            className="inline-flex h-9 items-center rounded-[var(--radius-md)] border border-border-default px-3 text-xs font-semibold"
          >
            Saha
          </Link>
        </div>
      </div>

      <DaySummaryPanel refreshKey={summaryKey} />

      {view === "kanban" ? (
        <div className="grid gap-3 xl:grid-cols-4">
          {GROUPS.map((group) => (
            <section
              key={group.key}
              className="flex min-h-[20rem] flex-col rounded-[var(--radius-lg)] border border-border-default bg-surface-secondary/40"
            >
              <header className="flex items-center justify-between px-3 py-2.5">
                <h2 className="text-sm font-semibold text-foreground">{group.title}</h2>
                <span className="rounded-full bg-surface-primary px-2 py-0.5 text-xs text-muted">
                  {board[group.key].length}
                </span>
              </header>
              <div className="flex-1 space-y-2 overflow-y-auto px-2 pb-2">
                {board[group.key].length === 0 ? (
                  <EmptyState title="Boş" description="Bu kolonda görev yok." />
                ) : (
                  board[group.key].map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      compact
                      actions={actionsFor(task)}
                    />
                  ))
                )}
              </div>
            </section>
          ))}
        </div>
      ) : null}

      {view === "list" ? (
        <div className="space-y-5">
          {GROUPS.map((group) => (
            <section key={group.key}>
              <header className="mb-2 flex items-center gap-2">
                <h2 className="text-sm font-semibold text-foreground">{group.title}</h2>
                <span className="text-xs text-muted">{board[group.key].length}</span>
              </header>
              {board[group.key].length === 0 ? (
                <EmptyState title="Kayıt yok" description="Bu grupta görev bulunmuyor." />
              ) : (
                <div className="space-y-2">
                  {board[group.key].map((task) => (
                    <TaskCard key={task.id} task={task} actions={actionsFor(task)} />
                  ))}
                </div>
              )}
            </section>
          ))}
        </div>
      ) : null}

      {view === "calendar" ? (
        <BoardCalendar tasks={allTasks} onSelect={(task) => setActive(task)} />
      ) : null}

      {active ? (
        <CompleteTaskModal
          task={active}
          onClose={() => setActive(null)}
          onDone={() => {
            setActive(null);
            toast({ title: "Görev tamamlandı", tone: "success" });
            void refresh();
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

      {postponeTask ? (
        <PostponeTaskModal
          task={postponeTask}
          onClose={() => setPostponeTask(null)}
          onDone={() => {
            setPostponeTask(null);
            void refresh();
          }}
        />
      ) : null}

      {assignTask ? (
        <AssignTaskModal
          task={assignTask}
          onClose={() => setAssignTask(null)}
          onDone={() => {
            setAssignTask(null);
            void refresh();
          }}
        />
      ) : null}
    </div>
  );
}

function BoardCalendar({
  tasks,
  onSelect,
}: {
  tasks: CollectionTask[];
  onSelect: (task: CollectionTask) => void;
}) {
  const [cursor, setCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const byDay = useMemo(() => {
    const map = new Map<string, CollectionTask[]>();
    for (const t of tasks) {
      const key = t.due_date.slice(0, 10);
      const list = map.get(key) || [];
      list.push(t);
      map.set(key, list);
    }
    return map;
  }, [tasks]);

  const days = useMemo(() => {
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
    return cells;
  }, [cursor]);

  const title = cursor.toLocaleDateString("tr-TR", { month: "long", year: "numeric" });
  const todayKey = localDayKey(new Date());

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          className="rounded-[var(--radius-md)] border border-border-default px-3 py-1.5 text-sm"
          onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}
        >
          ←
        </button>
        <span className="text-sm font-semibold capitalize">{title}</span>
        <button
          type="button"
          className="rounded-[var(--radius-md)] border border-border-default px-3 py-1.5 text-sm"
          onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
        >
          →
        </button>
      </div>
      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-[var(--radius-lg)] border border-border-default bg-border-default">
        {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((d) => (
          <div
            key={d}
            className="bg-surface-secondary px-2 py-2 text-center text-xs font-semibold text-subtle"
          >
            {d}
          </div>
        ))}
        {days.map((cell) => {
          const dayTasks = cell.date ? byDay.get(cell.key) || [] : [];
          return (
            <div
              key={cell.key}
              className={cn(
                "min-h-[5.5rem] bg-surface-primary p-1.5",
                cell.key === todayKey && "ring-1 ring-inset ring-brand/40",
              )}
            >
              {cell.date ? (
                <>
                  <p className="text-[11px] font-semibold text-muted">{cell.date.getDate()}</p>
                  <ul className="mt-1 space-y-0.5">
                    {dayTasks.slice(0, 3).map((t) => (
                      <li key={t.id}>
                        <button
                          type="button"
                          onClick={() => {
                            if (t.status !== "COMPLETED" && t.status !== "CANCELLED") {
                              onSelect(t);
                            }
                          }}
                          className="w-full truncate rounded px-1 py-0.5 text-left text-[10px] font-medium text-foreground hover:bg-surface-secondary"
                          title={t.customer_name}
                        >
                          {t.customer_name}
                        </button>
                      </li>
                    ))}
                    {dayTasks.length > 3 ? (
                      <li className="px-1 text-[10px] text-muted">+{dayTasks.length - 3}</li>
                    ) : null}
                  </ul>
                </>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
