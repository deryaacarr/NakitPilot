"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { listCustomers } from "@/lib/customers/api";
import type { Customer } from "@/lib/customers/types";
import { createPaymentPromise } from "@/lib/promises/api";

/** Opens inline create when ?create=1 (NP-381 quick action). */
export function PromiseQuickCreate() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customer, setCustomer] = useState("");
  const [amount, setAmount] = useState("");
  const [promisedDate, setPromisedDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (searchParams.get("create") === "1") setOpen(true);
  }, [searchParams]);

  useEffect(() => {
    if (!open) return;
    void listCustomers({ page_size: 100 }).then((res) => {
      if (res.ok) setCustomers(res.data.results || []);
    });
  }, [open]);

  if (!open) return null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!customer || !amount) return;
    setSaving(true);
    const res = await createPaymentPromise({
      customer: Number(customer),
      amount,
      promised_date: promisedDate,
      notes,
    });
    setSaving(false);
    if (!res.ok) {
      toast({ title: "Söz oluşturulamadı", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Ödeme sözü oluşturuldu", tone: "success" });
    setOpen(false);
    router.replace("/promises");
    router.refresh();
  }

  return (
    <form
      onSubmit={onSubmit}
      className="grid gap-3 rounded-[var(--radius-lg)] border border-border-default bg-surface-secondary p-4 sm:grid-cols-2"
    >
      <p className="text-sm font-semibold text-foreground sm:col-span-2">Yeni ödeme sözü</p>
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
        <span className="font-medium">Tutar</span>
        <Input required inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
      </label>
      <label className="block space-y-1 text-sm">
        <span className="font-medium">Söz tarihi</span>
        <Input
          type="date"
          required
          value={promisedDate}
          onChange={(e) => setPromisedDate(e.target.value)}
        />
      </label>
      <label className="block space-y-1 text-sm sm:col-span-2">
        <span className="font-medium">Not</span>
        <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <div className="flex gap-2 sm:col-span-2">
        <Button type="submit" loading={saving} disabled={saving}>
          Oluştur
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            setOpen(false);
            router.replace("/promises");
          }}
        >
          Vazgeç
        </Button>
      </div>
    </form>
  );
}
