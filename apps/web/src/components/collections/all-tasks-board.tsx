"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { StatusChip } from "@/components/ui/status-chip";
import { useToast } from "@/components/ui/toast";
import { listCollectionTasks } from "@/lib/collections/api";
import type { CollectionTask } from "@/lib/collections/types";
import { listCustomers } from "@/lib/customers/api";
import type { Customer } from "@/lib/customers/types";
import { apiRequest } from "@/lib/api/client";

export function AllTasksBoard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const [tasks, setTasks] = useState<CollectionTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customer, setCustomer] = useState("");
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await listCollectionTasks({ page_size: 100 });
    setLoading(false);
    if (res.ok) setTasks(res.data.results || []);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (searchParams.get("create") === "1") setCreateOpen(true);
    const preselect = searchParams.get("customer");
    if (preselect) setCustomer(preselect);
  }, [searchParams]);

  useEffect(() => {
    if (!createOpen) return;
    void listCustomers({ page_size: 100 }).then((res) => {
      if (res.ok) setCustomers(res.data.results || []);
    });
  }, [createOpen]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!customer) return;
    setSaving(true);
    const res = await apiRequest<CollectionTask>("/api/collection-tasks/", {
      method: "POST",
      body: {
        customer: Number(customer),
        title: title || "Tahsilat görevi",
        due_date: dueDate,
        task_type: "CALL",
      },
    });
    setSaving(false);
    if (!res.ok) {
      toast({ title: "Görev oluşturulamadı", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Görev oluşturuldu", tone: "success" });
    setCreateOpen(false);
    router.replace("/collections/tasks");
    void load();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl tracking-tight text-foreground">Tüm görevler</h1>
          <p className="mt-1 text-sm text-muted">Tahsilat görevlerinin tamamı</p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          + Yeni görev
        </Button>
      </div>

      {createOpen ? (
        <form
          onSubmit={onCreate}
          className="grid gap-3 rounded-[var(--radius-lg)] border border-border-default bg-surface-secondary p-4 sm:grid-cols-2"
        >
          <label className="block space-y-1 text-sm sm:col-span-2">
            <span className="font-medium">Müşteri</span>
            <select
              required
              value={customer}
              onChange={(e) => setCustomer(e.target.value)}
              className="h-10 w-full rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3"
            >
              <option value="">Seçin</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1 text-sm">
            <span className="font-medium">Başlık</span>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Arama / takip" />
          </label>
          <label className="block space-y-1 text-sm">
            <span className="font-medium">Vade</span>
            <Input type="date" required value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </label>
          <div className="flex gap-2 sm:col-span-2">
            <Button type="submit" loading={saving} disabled={saving}>
              Oluştur
            </Button>
            <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>
              Vazgeç
            </Button>
          </div>
        </form>
      ) : null}

      {loading ? (
        <LoadingSkeleton className="h-48" />
      ) : (
        <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border-default">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-secondary text-xs uppercase tracking-wide text-subtle">
              <tr>
                <th className="px-4 py-3 font-semibold">Görev</th>
                <th className="px-4 py-3 font-semibold">Müşteri</th>
                <th className="px-4 py-3 font-semibold">Vade</th>
                <th className="px-4 py-3 font-semibold">Durum</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id} className="border-t border-border-default">
                  <td className="px-4 py-3 font-medium">{t.title}</td>
                  <td className="px-4 py-3">
                    <Link href={`/customers/${t.customer}`} className="text-primary hover:underline">
                      {t.customer_name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted">{t.due_date}</td>
                  <td className="px-4 py-3">
                    <StatusChip
                      tone={
                        t.status === "COMPLETED"
                          ? "success"
                          : t.status === "CANCELLED"
                            ? "neutral"
                            : t.status === "OVERDUE"
                              ? "danger"
                              : "info"
                      }
                      label={t.status}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
