"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { listCustomers } from "@/lib/customers/api";
import type { Customer } from "@/lib/customers/types";
import { createPayment } from "@/lib/payments/api";

export function PaymentCreateForm() {
  const router = useRouter();
  const { toast } = useToast();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customer, setCustomer] = useState("");
  const [paymentDate, setPaymentDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void listCustomers({ page_size: 100 }).then((res) => {
      if (res.ok) setCustomers(res.data.results || []);
    });
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!customer || !amount) return;
    setSaving(true);
    const res = await createPayment({
      customer: Number(customer),
      payment_date: paymentDate,
      amount,
      reference,
      notes,
      auto_allocate: true,
    });
    setSaving(false);
    if (!res.ok) {
      toast({ title: "Ödeme kaydedilemedi", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Ödeme kaydedildi", tone: "success" });
    router.push("/payments");
  }

  return (
    <form onSubmit={onSubmit} className="max-w-lg space-y-4">
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium text-foreground">Müşteri</span>
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
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium text-foreground">Tarih</span>
        <Input type="date" required value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium text-foreground">Tutar</span>
        <Input required inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium text-foreground">Referans</span>
        <Input value={reference} onChange={(e) => setReference(e.target.value)} />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium text-foreground">Not</span>
        <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <div className="flex gap-2">
        <Button type="submit" disabled={saving} loading={saving}>
          Kaydet
        </Button>
        <Button type="button" variant="secondary" onClick={() => router.push("/payments")}>
          İptal
        </Button>
      </div>
    </form>
  );
}
