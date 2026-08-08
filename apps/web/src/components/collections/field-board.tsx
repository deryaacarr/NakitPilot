"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CompleteTaskModal } from "@/components/collections/complete-task-modal";
import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import { confirmCollectionNotes, fetchTodayBoard } from "@/lib/collections/api";
import { syncOfflineQueue } from "@/lib/collections/offline-api";
import type { CollectionTask, TodayBoard } from "@/lib/collections/types";
import { formatDate, formatMoney } from "@/lib/customers/format";
import type { AppError } from "@/lib/errors";
import {
  enqueueOffline,
  listOfflineQueue,
  newClientId,
  removeOfflineItems,
  type OfflineQueueItem,
} from "@/lib/pwa/offline-queue";
import { subscribeWebPush } from "@/lib/pwa/push";
import { createPaymentPromise } from "@/lib/promises/api";

type Tab = "tasks" | "search" | "queue";

function telHref(phone: string) {
  const cleaned = phone.replace(/[^\d+]/g, "");
  return cleaned ? `tel:${cleaned}` : "";
}

export function FieldBoard() {
  const { toast } = useToast();
  const [board, setBoard] = useState<TodayBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [tab, setTab] = useState<Tab>("tasks");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<
    Array<{ id: number; name: string; phone: string; code: string }>
  >([]);
  const [active, setActive] = useState<CollectionTask | null>(null);
  const [noteTask, setNoteTask] = useState<CollectionTask | null>(null);
  const [noteText, setNoteText] = useState("");
  const [promiseTask, setPromiseTask] = useState<CollectionTask | null>(null);
  const [promiseAmount, setPromiseAmount] = useState("");
  const [promiseDate, setPromiseDate] = useState("");
  const [postCallTask, setPostCallTask] = useState<CollectionTask | null>(null);
  const [queue, setQueue] = useState<OfflineQueueItem[]>([]);
  const [conflicts, setConflicts] = useState<
    Array<{ client_id: string; reason: string; server?: Record<string, unknown> }>
  >([]);
  const [online, setOnline] = useState(
    typeof navigator === "undefined" ? true : navigator.onLine,
  );

  const loadQueue = useCallback(async () => {
    setQueue(await listOfflineQueue());
  }, []);

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

  const flushQueue = useCallback(async () => {
    const items = await listOfflineQueue();
    if (!items.length) return;
    if (!navigator.onLine) return;
    const result = await syncOfflineQueue(items);
    if (!result.ok) {
      toast({ title: "Senkron başarısız", description: result.error.message, tone: "error" });
      return;
    }
    const syncedIds = (result.data.synced || [])
      .map((row) => String(row.client_id || ""))
      .filter(Boolean);
    await removeOfflineItems(syncedIds);
    setConflicts(result.data.conflicts || []);
    await loadQueue();
    await load();
    if (result.data.conflicts?.length) {
      toast({
        title: "Çakışmalar var",
        description: `${result.data.conflicts.length} kayıt kullanıcı onayı bekliyor.`,
        tone: "warning",
      });
    } else if (syncedIds.length) {
      toast({ title: "Senkron tamam", description: `${syncedIds.length} kayıt işlendi.`, tone: "success" });
    }
  }, [load, loadQueue, toast]);

  useEffect(() => {
    void load();
    void loadQueue();
    const onOnline = () => {
      setOnline(true);
      void flushQueue();
    };
    const onOffline = () => setOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [load, loadQueue, flushQueue]);

  const tasks = useMemo(() => {
    if (!board) return [];
    return [...board.overdue, ...board.today, ...board.upcoming];
  }, [board]);

  async function searchCustomers(q: string) {
    setQuery(q);
    if (q.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    const result = await apiRequest<{
      results: Array<{ id: number; name: string; phone: string; code: string }>;
    }>("/api/customers/", { query: { search: q.trim(), page_size: 20 } });
    if (result.ok) setSearchResults(result.data.results || []);
  }

  async function saveNote(task: CollectionTask, notes: string) {
    if (!notes.trim()) return;
    if (!navigator.onLine) {
      await enqueueOffline({
        client_id: newClientId(),
        kind: "NOTE",
        task_id: task.id,
        customer_id: task.customer,
        payload: { notes },
        base_updated_at: null,
      });
      await loadQueue();
      toast({
        title: "Not kuyruğa alındı",
        description: "Bağlantı gelince senkronize edilecek.",
        tone: "default",
      });
      setNoteTask(null);
      setNoteText("");
      return;
    }
    const result = await confirmCollectionNotes(task.id, {
      raw_notes: notes,
      confirmed: true,
      complete_task: false,
    });
    if (!result.ok) {
      toast({ title: "Not kaydedilemedi", description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "Görüşme notu kaydedildi", tone: "success" });
    setNoteTask(null);
    setNoteText("");
    void load();
  }

  async function savePromise(task: CollectionTask) {
    if (!promiseAmount || !promiseDate) {
      toast({ title: "Tutar ve tarih gerekli", tone: "warning" });
      return;
    }
    if (!navigator.onLine) {
      await enqueueOffline({
        client_id: newClientId(),
        kind: "PROMISE_DRAFT",
        task_id: task.id,
        customer_id: task.customer,
        payload: {
          amount: promiseAmount,
          promised_date: promiseDate,
          notes: "Saha taslak sözü",
        },
      });
      await loadQueue();
      toast({ title: "Ödeme sözü taslağı kuyruğa alındı", tone: "default" });
      setPromiseTask(null);
      return;
    }
    const result = await createPaymentPromise({
      customer: task.customer,
      amount: promiseAmount,
      promised_date: promiseDate,
      notes: "Saha ödeme sözü",
    });
    if (!result.ok) {
      toast({ title: "Söz kaydedilemedi", description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "Ödeme sözü eklendi", tone: "success" });
    setPromiseTask(null);
    setPromiseAmount("");
    setPromiseDate("");
    void load();
  }

  if (loading) return <LoadingSkeleton lines={8} />;
  if (error && !board) return <ErrorState error={error} onRetry={() => void load()} />;

  return (
    <div className="mx-auto max-w-lg space-y-4 pb-24">
      <header className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              NakitPilot
            </p>
            <h1 className="font-serif text-3xl tracking-tight text-slate-900">Saha tahsilat</h1>
            <p className="mt-1 text-sm text-slate-600">
              Bugünkü görevler, arama ve çevrimdışı notlar
            </p>
          </div>
          <Badge tone={online ? "success" : "warning"}>{online ? "Çevrimiçi" : "Çevrimdışı"}</Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={() => void subscribeWebPush()}>
            Bildirimleri aç
          </Button>
          <Link
            href="/collections"
            className="inline-flex h-8 items-center rounded-lg px-3 text-xs font-semibold text-slate-700 hover:bg-slate-100"
          >
            Klasik pano
          </Link>
        </div>
      </header>

      <nav className="grid grid-cols-3 gap-1 rounded-xl bg-slate-100 p-1">
        {(
          [
            ["tasks", "Görevler"],
            ["search", "Arama"],
            ["queue", `Kuyruk (${queue.length})`],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`rounded-lg px-2 py-2 text-sm font-medium ${
              tab === id ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {conflicts.length > 0 ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-3">
          <h2 className="text-sm font-semibold text-amber-950">Senkron çakışmaları</h2>
          <ul className="mt-2 space-y-2 text-xs text-amber-900">
            {conflicts.map((c) => (
              <li key={c.client_id} className="rounded-lg bg-white/70 p-2">
                <p className="font-medium">{c.reason}</p>
                <p className="mt-1 text-amber-800/80">{c.client_id}</p>
                {c.server?.outcome_notes ? (
                  <p className="mt-1">Sunucu notu: {String(c.server.outcome_notes)}</p>
                ) : null}
              </li>
            ))}
          </ul>
          <Button size="sm" className="mt-2" variant="secondary" onClick={() => setConflicts([])}>
            Anlaşıldı
          </Button>
        </section>
      ) : null}

      {tab === "tasks" ? (
        <section className="space-y-3">
          {tasks.length === 0 ? (
            <EmptyState
              title="Bugün görev yok"
              description="Atanan açık tahsilat görevi bulunmuyor."
            />
          ) : (
            tasks.map((task) => (
              <article
                key={task.id}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">{task.customer_name}</h2>
                    <p className="text-xs text-slate-500">{task.title}</p>
                  </div>
                  <Badge
                    tone={
                      task.priority === "CRITICAL" || task.priority === "HIGH"
                        ? "danger"
                        : "neutral"
                    }
                  >
                    {task.priority}
                  </Badge>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                  <div>
                    <dt>Vade</dt>
                    <dd className="font-medium text-slate-900">{formatDate(task.due_date)}</dd>
                  </div>
                  <div>
                    <dt>Bakiye</dt>
                    <dd className="font-medium text-slate-900">
                      {formatMoney(task.overdue_balance)}
                    </dd>
                  </div>
                </dl>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {task.customer_phone ? (
                    <Button
                      size="sm"
                      onClick={() => {
                        const href = telHref(task.customer_phone!);
                        if (!href) return;
                        window.location.href = href;
                        window.setTimeout(() => setPostCallTask(task), 800);
                      }}
                    >
                      Ara
                    </Button>
                  ) : (
                    <Button size="sm" variant="secondary" disabled>
                      Telefon yok
                    </Button>
                  )}
                  <Button size="sm" variant="secondary" onClick={() => setNoteTask(task)}>
                    Görüşme notu
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setPromiseTask(task)}>
                    Ödeme sözü
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      if (!navigator.onLine) {
                        await enqueueOffline({
                          client_id: newClientId(),
                          kind: "COMPLETE_TASK",
                          task_id: task.id,
                          customer_id: task.customer,
                          payload: {
                            outcome: "REACHED",
                            outcome_notes: "Offline tamamlandı",
                          },
                        });
                        await loadQueue();
                        toast({ title: "Tamamlama kuyruğa alındı", tone: "default" });
                        return;
                      }
                      setActive(task);
                    }}
                  >
                    Tamamla
                  </Button>
                </div>
                {task.customer_phone ? (
                  <p className="mt-2 text-xs text-slate-500">{task.customer_phone}</p>
                ) : null}
              </article>
            ))
          )}
        </section>
      ) : null}

      {tab === "search" ? (
        <section className="space-y-3">
          <input
            value={query}
            onChange={(e) => void searchCustomers(e.target.value)}
            placeholder="Müşteri adı, telefon, kod…"
            className="w-full rounded-xl border border-slate-200 px-3 py-3 text-sm outline-none ring-slate-300 focus:ring-2"
          />
          {searchResults.length === 0 ? (
            <EmptyState title="Arama yapın" description="En az 2 karakter girin." />
          ) : (
            searchResults.map((c) => (
              <div key={c.id} className="rounded-xl border border-slate-200 bg-white p-3">
                <p className="font-medium text-slate-900">{c.name}</p>
                <p className="text-xs text-slate-500">{c.code || "—"}</p>
                <div className="mt-2 flex gap-2">
                  {c.phone ? (
                    <a
                      href={telHref(c.phone)}
                      className="inline-flex h-8 items-center rounded-lg bg-brand px-3 text-xs font-semibold text-white"
                    >
                      Ara
                    </a>
                  ) : null}
                  <Link
                    href={`/customers/${c.id}`}
                    className="inline-flex h-8 items-center rounded-lg bg-slate-100 px-3 text-xs font-semibold text-slate-800"
                  >
                    Detay
                  </Link>
                </div>
              </div>
            ))
          )}
        </section>
      ) : null}

      {tab === "queue" ? (
        <section className="space-y-3">
          <Button
            onClick={async () => {
              if (!queue.length) {
                toast({ title: "Kuyruk boş", tone: "default" });
                return;
              }
              await flushQueue();
            }}
            disabled={!queue.length}
          >
            Şimdi senkronize et
          </Button>
          {queue.length === 0 ? (
            <EmptyState
              title="Bekleyen kayıt yok"
              description="Çevrimdışı notlar burada görünür."
            />
          ) : (
            queue.map((item) => (
              <div
                key={item.client_id}
                className="rounded-xl border border-slate-200 bg-white p-3 text-sm"
              >
                <p className="font-medium">{item.kind}</p>
                <p className="text-xs text-slate-500">{item.client_id}</p>
                <pre className="mt-2 overflow-auto rounded bg-slate-50 p-2 text-[11px] text-slate-700">
                  {JSON.stringify(item.payload, null, 2)}
                </pre>
              </div>
            ))
          )}
        </section>
      ) : null}

      {noteTask ? (
        <div className="fixed inset-0 z-50 flex items-end bg-black/40 p-3 sm:items-center sm:justify-center">
          <div className="w-full max-w-md rounded-2xl bg-white p-4">
            <h3 className="font-semibold text-slate-900">
              Görüşme notu — {noteTask.customer_name}
            </h3>
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              rows={5}
              className="mt-3 w-full rounded-xl border border-slate-200 p-3 text-sm"
              placeholder="Görüşme özeti…"
            />
            <div className="mt-3 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setNoteTask(null)}>
                Vazgeç
              </Button>
              <Button onClick={() => void saveNote(noteTask, noteText)}>Kaydet</Button>
            </div>
          </div>
        </div>
      ) : null}

      {promiseTask ? (
        <div className="fixed inset-0 z-50 flex items-end bg-black/40 p-3 sm:items-center sm:justify-center">
          <div className="w-full max-w-md rounded-2xl bg-white p-4">
            <h3 className="font-semibold text-slate-900">
              Ödeme sözü — {promiseTask.customer_name}
            </h3>
            <div className="mt-3 space-y-2">
              <input
                type="number"
                value={promiseAmount}
                onChange={(e) => setPromiseAmount(e.target.value)}
                placeholder="Tutar"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
              />
              <input
                type="date"
                value={promiseDate}
                onChange={(e) => setPromiseDate(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setPromiseTask(null)}>
                Vazgeç
              </Button>
              <Button onClick={() => void savePromise(promiseTask)}>Ekle</Button>
            </div>
          </div>
        </div>
      ) : null}

      {postCallTask ? (
        <div className="fixed inset-0 z-50 flex items-end bg-black/40 p-3 sm:items-center sm:justify-center">
          <div className="w-full max-w-md rounded-2xl bg-white p-4">
            <h3 className="font-semibold text-slate-900">
              Görüşme sonucunu kaydetmek ister misiniz?
            </h3>
            <p className="mt-1 text-sm text-slate-600">{postCallTask.customer_name}</p>
            <div className="mt-4 grid gap-2">
              <Button
                onClick={() => {
                  setNoteTask(postCallTask);
                  setPostCallTask(null);
                }}
              >
                Görüşme notu yaz
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setActive(postCallTask);
                  setPostCallTask(null);
                }}
              >
                Görevi tamamla
              </Button>
              <Button variant="ghost" onClick={() => setPostCallTask(null)}>
                Şimdilik geç
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {active ? (
        <CompleteTaskModal
          task={active}
          onClose={() => setActive(null)}
          onDone={() => {
            setActive(null);
            void load();
          }}
        />
      ) : null}
    </div>
  );
}
