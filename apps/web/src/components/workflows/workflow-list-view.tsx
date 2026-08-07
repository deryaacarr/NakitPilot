"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { SkeletonBlock } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import {
  createWorkflow,
  getWorkflowMeta,
  listWorkflows,
  statusLabel,
  unwrapList,
  type WorkflowMeta,
  type WorkflowSummary,
} from "@/lib/workflows/api";

const TRIGGER_FALLBACK = [
  { value: "invoice_overdue", label: "Fatura gecikti" },
  { value: "promise_broken", label: "Ödeme sözü bozuldu" },
  { value: "promise_made", label: "Ödeme sözü verildi" },
  { value: "payment_received", label: "Yeni ödeme geldi" },
  { value: "risk_level_changed", label: "Risk seviyesi değişti" },
  { value: "customer_unreachable", label: "Müşteriye ulaşılamadı" },
  { value: "open_balance_exceeded", label: "Açık bakiye limiti aştı" },
  { value: "manual", label: "Manuel" },
];

export function WorkflowListView() {
  const { toast } = useToast();
  const [items, setItems] = useState<WorkflowSummary[]>([]);
  const [meta, setMeta] = useState<WorkflowMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState("invoice_overdue");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [listRes, metaRes] = await Promise.all([listWorkflows(), getWorkflowMeta()]);
    if (!listRes.ok) {
      setError(listRes.error.message);
      setLoading(false);
      return;
    }
    setItems(unwrapList(listRes.data));
    if (metaRes.ok) setMeta(metaRes.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate() {
    if (!name.trim()) {
      toast({ title: "İsim gerekli", tone: "error" });
      return;
    }
    setCreating(true);
    const wf = await createWorkflow({
      name: name.trim(),
      trigger_type: trigger,
      description: "",
    });
    setCreating(false);
    if (!wf.ok) {
      toast({ title: "Oluşturulamadı", description: wf.error.message, tone: "error" });
      return;
    }
    toast({ title: "İş akışı oluşturuldu", tone: "success" });
    window.location.href = `/dashboard/workflows/${wf.data.id}`;
  }

  if (loading) return <SkeletonBlock className="h-64 w-full" />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;

  const triggers = meta?.triggers?.length ? meta.triggers : TRIGGER_FALLBACK;

  return (
    <div className="space-y-8">
      <section className="border-b border-slate-200 pb-8">
        <h2 className="font-serif text-xl text-slate-900">Yeni akış</h2>
        <p className="mt-1 text-sm text-slate-600">
          Kod yazmadan tetikleyici, koşul ve aksiyon bloklarıyla tahsilat akışı kurun.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="block min-w-[200px] flex-1 text-sm">
            <span className="mb-1 block text-slate-600">Ad</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Örn. 30 gün eskalasyon" />
          </label>
          <div className="min-w-[220px]">
            <Select
              label="Tetikleyici"
              value={trigger}
              onChange={(e) => setTrigger(e.target.value)}
              options={triggers}
            />
          </div>
          <Button type="button" onClick={() => void onCreate()} disabled={creating}>
            {creating ? "Oluşturuluyor…" : "Oluştur ve düzenle"}
          </Button>
        </div>
      </section>

      <section>
        <h2 className="font-serif text-xl text-slate-900">Kayıtlı akışlar</h2>
        {items.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">Henüz iş akışı yok.</p>
        ) : (
          <ul className="mt-4 divide-y divide-slate-200 border-t border-slate-200">
            {items.map((wf) => (
              <li key={wf.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                <div>
                  <Link
                    href={`/dashboard/workflows/${wf.id}`}
                    className="font-medium text-teal-800 underline-offset-2 hover:underline"
                  >
                    {wf.name}
                  </Link>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {triggers.find((t) => t.value === wf.trigger_type)?.label ?? wf.trigger_type}
                    {" · "}
                    {statusLabel(wf.status)} v{wf.version}
                    {" · "}
                    {wf.step_count} blok
                  </p>
                </div>
                <Link href={`/dashboard/workflows/${wf.id}`}>
                  <Button type="button" variant="secondary">
                    Düzenle
                  </Button>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
