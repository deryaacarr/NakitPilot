"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import { listCustomers } from "@/lib/customers/api";
import { formatMoney } from "@/lib/customers/format";
import type { Customer } from "@/lib/customers/types";
import { listInvoices } from "@/lib/invoices/api";
import type { Invoice } from "@/lib/invoices/types";
import {
  createPaymentPromise,
  listPaymentPromises,
  normalizeCreatePromiseResponse,
} from "@/lib/promises/api";
import { formatDate } from "@/lib/customers/format";

type MembershipRow = {
  user_id: number;
  user_email: string;
  user_name?: string;
  organization: number;
};

type SameDatePromise = {
  id: number;
  amount: string;
  currency: string;
  status: string;
};

/** NP-430 — full promise create with balance/same-date checks + follow-up task. */
export function PromiseCreateForm({
  onCreated,
  defaultOpen,
}: {
  onCreated?: () => void;
  defaultOpen?: boolean;
}) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { toast } = useToast();
  const [open, setOpen] = useState(Boolean(defaultOpen));
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [assignees, setAssignees] = useState<MembershipRow[]>([]);
  const [customer, setCustomer] = useState("");
  const [invoice, setInvoice] = useState("");
  const [amount, setAmount] = useState("");
  const [promisedDate, setPromisedDate] = useState(
    () => searchParams.get("date") || new Date().toISOString().slice(0, 10),
  );
  const [notes, setNotes] = useState("");
  const [assignee, setAssignee] = useState("");
  const [createFollowUp, setCreateFollowUp] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sameDate, setSameDate] = useState<SameDatePromise[]>([]);

  useEffect(() => {
    if (searchParams.get("create") === "1") setOpen(true);
    const preselect = searchParams.get("customer");
    if (preselect) setCustomer(preselect);
    const date = searchParams.get("date");
    if (date) setPromisedDate(date);
  }, [searchParams]);

  useEffect(() => {
    if (!open) return;
    void listCustomers({ page_size: 100 }).then((res) => {
      if (res.ok) setCustomers(res.data.results || []);
    });
    void (async () => {
      const memberships = await apiRequest<MembershipRow[]>("/api/memberships/me/");
      if (!memberships.ok || memberships.data.length === 0) return;
      const orgId = memberships.data[0].organization;
      const orgMembers = await apiRequest<MembershipRow[] | { results?: MembershipRow[] }>(
        `/api/organizations/${orgId}/memberships/`,
      );
      if (!orgMembers.ok) return;
      setAssignees(
        Array.isArray(orgMembers.data)
          ? orgMembers.data
          : (orgMembers.data.results ?? []),
      );
    })();
  }, [open]);

  useEffect(() => {
    if (!customer) {
      setInvoices([]);
      setInvoice("");
      return;
    }
    void listInvoices({ customer: Number(customer), page_size: 50 }).then((res) => {
      if (!res.ok) return;
      const openOnes = (res.data.results || []).filter(
        (inv) => !["PAID", "CANCELLED", "DRAFT"].includes(inv.status),
      );
      setInvoices(openOnes);
    });
  }, [customer]);

  useEffect(() => {
    if (!customer || !promisedDate) {
      setSameDate([]);
      return;
    }
    void listPaymentPromises({
      customer: Number(customer),
      promised_date_from: promisedDate,
      promised_date_to: promisedDate,
      page_size: 20,
    }).then((res) => {
      if (!res.ok) return;
      setSameDate(
        (res.data.results || []).map((p) => ({
          id: p.id,
          amount: p.amount,
          currency: p.currency,
          status: p.status,
        })),
      );
    });
  }, [customer, promisedDate]);

  const selectedCustomer = useMemo(
    () => customers.find((c) => String(c.id) === customer) || null,
    [customers, customer],
  );

  const openBalance = selectedCustomer?.open_balance ?? null;
  const amountNum = Number(amount);
  const exceedsBalance =
    openBalance != null && Number.isFinite(amountNum) && amountNum > Number(openBalance);

  if (!open) {
    return (
      <div className="flex justify-end">
        <Button type="button" onClick={() => setOpen(true)}>
          Yeni ödeme sözü
        </Button>
      </div>
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!customer || !amount) return;
    setSaving(true);
    const res = await createPaymentPromise({
      customer: Number(customer),
      amount,
      promised_date: promisedDate,
      notes,
      invoice: invoice ? Number(invoice) : null,
      create_follow_up: createFollowUp,
      assigned_to: assignee ? Number(assignee) : null,
      follow_up_due_date: createFollowUp ? promisedDate : null,
    });
    setSaving(false);
    if (!res.ok) {
      toast({ title: "Söz oluşturulamadı", description: res.error.message, tone: "error" });
      return;
    }
    const payload = normalizeCreatePromiseResponse(res.data);
    const warns = payload.warnings || {};
    if (warns.amount_exceeds_open_balance) {
      toast({
        title: "Uyarı: tutar açık bakiyeyi aşıyor",
        description: String(
          (warns.amount_exceeds_open_balance as { detail?: string }).detail || "",
        ),
        tone: "warning",
      });
    }
    if (warns.same_date_promises) {
      toast({
        title: "Aynı tarihte mevcut sözler var",
        description: String((warns.same_date_promises as { detail?: string }).detail || ""),
        tone: "warning",
      });
    }
    toast({
      title: payload.follow_up_task_id
        ? "Ödeme sözü ve takip görevi oluşturuldu"
        : "Ödeme sözü oluşturuldu",
      tone: "success",
    });
    setOpen(false);
    router.replace("/promises");
    onCreated?.();
  }

  return (
    <form
      onSubmit={onSubmit}
      className="grid gap-3 rounded-[var(--radius-lg)] border border-border-default bg-surface-secondary p-4 sm:grid-cols-2"
    >
      <div className="sm:col-span-2">
        <p className="text-sm font-semibold text-foreground">Yeni ödeme sözü</p>
        {openBalance != null ? (
          <p className="mt-1 text-xs text-muted">
            Açık bakiye:{" "}
            <span className="font-semibold text-foreground">{formatMoney(openBalance)}</span>
          </p>
        ) : null}
      </div>

      <label className="block space-y-1 text-sm sm:col-span-2">
        <span className="font-medium">Müşteri *</span>
        <select
          required
          value={customer}
          onChange={(e) => {
            setCustomer(e.target.value);
            setInvoice("");
            const c = customers.find((x) => String(x.id) === e.target.value);
            if (c?.assigned_user) setAssignee(String(c.assigned_user));
          }}
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

      <label className="block space-y-1 text-sm sm:col-span-2">
        <span className="font-medium">Fatura</span>
        <select
          value={invoice}
          onChange={(e) => {
            setInvoice(e.target.value);
            const inv = invoices.find((x) => String(x.id) === e.target.value);
            if (inv) setAmount(inv.remaining_amount);
          }}
          className="h-10 w-full rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3"
          disabled={!customer}
        >
          <option value="">Fatura seçilmedi</option>
          {invoices.map((inv) => (
            <option key={inv.id} value={inv.id}>
              {inv.number} · {formatMoney(inv.remaining_amount)} · vade {formatDate(inv.due_date)}
            </option>
          ))}
        </select>
      </label>

      <label className="block space-y-1 text-sm">
        <span className="font-medium">Söz verilen tutar *</span>
        <Input
          required
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        {exceedsBalance ? (
          <span className="text-xs text-danger-foreground">
            Tutar açık bakiyeyi ({formatMoney(openBalance)}) aşıyor.
          </span>
        ) : null}
      </label>

      <label className="block space-y-1 text-sm">
        <span className="font-medium">Söz tarihi *</span>
        <Input
          type="date"
          required
          value={promisedDate}
          onChange={(e) => setPromisedDate(e.target.value)}
        />
      </label>

      <label className="block space-y-1 text-sm sm:col-span-2">
        <span className="font-medium">Açıklama</span>
        <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>

      <label className="block space-y-1 text-sm sm:col-span-2">
        <span className="font-medium">Takip sorumlusu</span>
        <select
          value={assignee}
          onChange={(e) => setAssignee(e.target.value)}
          className="h-10 w-full rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3"
        >
          <option value="">Müşteri sorumlusu / oluşturan</option>
          {assignees.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.user_name || m.user_email}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2 text-sm sm:col-span-2">
        <input
          type="checkbox"
          checked={createFollowUp}
          onChange={(e) => setCreateFollowUp(e.target.checked)}
        />
        Takip görevi oluştur (söz tarihinde)
      </label>

      {sameDate.length ? (
        <div className="rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3 py-2 text-xs sm:col-span-2">
          <p className="font-semibold text-foreground">
            Aynı tarihte {sameDate.length} mevcut söz:
          </p>
          <ul className="mt-1 space-y-0.5 text-muted">
            {sameDate.map((p) => (
              <li key={p.id}>
                #{p.id} · {formatMoney(p.amount, p.currency)} · {p.status}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

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
