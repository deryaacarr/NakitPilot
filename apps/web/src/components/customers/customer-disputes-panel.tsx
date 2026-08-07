"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  createDispute,
  listDisputeCategories,
  listDisputes,
  resolveDispute,
  type Dispute,
  type DisputeCategory,
} from "@/lib/customers/communication";
import type { AppError } from "@/lib/errors";

type Props = { customerId: number };

function asList(data: Dispute[] | { results: Dispute[] }): Dispute[] {
  return Array.isArray(data) ? data : data.results ?? [];
}

export function CustomerDisputesPanel({ customerId }: Props) {
  const { toast } = useToast();
  const [rows, setRows] = useState<Dispute[]>([]);
  const [categories, setCategories] = useState<DisputeCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [category, setCategory] = useState("INVOICE_ERROR");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const [d, c] = await Promise.all([
      listDisputes({ customer_id: customerId }),
      listDisputeCategories(),
    ]);
    setLoading(false);
    if (!d.ok) {
      setError(d.error);
      return;
    }
    setError(null);
    setRows(asList(d.data));
    if (c.ok) {
      setCategories(c.data.results);
      if (c.data.results[0] && !category) {
        setCategory(c.data.results[0].value);
      }
    }
  }, [customerId, category]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId]);

  const onCreate = async () => {
    setSaving(true);
    const result = await createDispute({
      customer: customerId,
      category,
      amount: amount || undefined,
      description,
    });
    setSaving(false);
    if (!result.ok) {
      toast({ title: "İtiraz açılamadı", description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "İtiraz kaydı oluşturuldu", tone: "success" });
    setDescription("");
    setAmount("");
    void load();
  };

  const onResolve = async (id: number) => {
    const result = await resolveDispute(id, {
      status: "RESOLVED",
      resolution_note: "Çözüldü",
    });
    if (!result.ok) {
      toast({ title: "Çözülemedi", description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "İtiraz çözüldü", tone: "success" });
    void load();
  };

  if (loading) return <LoadingSkeleton className="h-32" />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;

  return (
    <div className="space-y-4">
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="text-xs text-slate-600">
          Kategori
          <select
            className="mt-1 w-full rounded-md border border-slate-200 px-2 py-2 text-sm"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {categories.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-600">
          Tutar
          <Input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />
        </label>
      </div>
      <Textarea
        placeholder="Açıklama"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <Button type="button" onClick={() => void onCreate()} disabled={saving}>
        {saving ? "Kaydediliyor…" : "İtiraz aç"}
      </Button>

      {rows.length === 0 ? (
        <EmptyState title="İtiraz yok" description="Bu müşteri için açık/kapalı itiraz kaydı bulunmuyor." />
      ) : (
        <ul className="space-y-2">
          {rows.map((d) => (
            <li
              key={d.id}
              className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-900">{d.category_label}</span>
                  <Badge
                    tone={
                      ["OPEN", "UNDER_REVIEW", "WAITING_CUSTOMER", "WAITING_INTERNAL"].includes(
                        d.status,
                      )
                        ? "warning"
                        : "neutral"
                    }
                  >
                    {d.status_label}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-slate-600">
                  {d.invoice_number ? `Fatura ${d.invoice_number} · ` : ""}
                  {d.amount ? `${d.amount} · ` : ""}
                  {d.description || "—"}
                </p>
              </div>
              {["OPEN", "UNDER_REVIEW", "WAITING_CUSTOMER", "WAITING_INTERNAL"].includes(
                d.status,
              ) && (
                <Button type="button" variant="outline" size="sm" onClick={() => void onResolve(d.id)}>
                  Çöz
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
