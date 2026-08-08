"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Money } from "@/components/ui/money";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { RISK_LABELS, type RiskStatus } from "@/lib/customers/types";
import type { CallListRow } from "@/lib/dashboard/types";
import { cn } from "@/lib/cn";

function riskTone(status: string) {
  if (status === "LOW") return "success" as const;
  if (status === "MEDIUM") return "warning" as const;
  if (status === "HIGH" || status === "CRITICAL") return "danger" as const;
  return "neutral" as const;
}

type Props = {
  rows: CallListRow[];
  currency: string;
  onChanged?: () => void;
};

export function CallPriorityPanel({ rows, currency, onChanged }: Props) {
  const top = rows.slice(0, 5);
  const rest = rows.slice(5);
  const [noteFor, setNoteFor] = useState<CallListRow | null>(null);
  const [note, setNote] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const { toast } = useToast();
  const router = useRouter();

  async function deferTask(row: CallListRow) {
    if (!row.open_task_id) {
      toast({
        title: "Ertelenecek açık görev yok",
        description: "Müşteri için önce görev oluşturun.",
        tone: "warning",
      });
      return;
    }
    setBusyId(row.customer_id);
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const due = tomorrow.toISOString().slice(0, 10);
    const res = await apiRequest(`/api/collection-tasks/${row.open_task_id}/`, {
      method: "PATCH",
      body: { due_date: due },
    });
    setBusyId(null);
    if (!res.ok) {
      toast({ title: "Erteleme başarısız", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Görev yarına ertelendi", tone: "success" });
    onChanged?.();
  }

  async function saveNote() {
    if (!noteFor || !note.trim()) return;
    // Prefer completing via customer page note flow — store as task description append when task exists
    if (noteFor.open_task_id) {
      setBusyId(noteFor.customer_id);
      const res = await apiRequest(`/api/collection-tasks/${noteFor.open_task_id}/`, {
        method: "PATCH",
        body: { description: note.trim() },
      });
      setBusyId(null);
      if (!res.ok) {
        toast({ title: "Not kaydedilemedi", description: res.error.message, tone: "error" });
        return;
      }
      toast({ title: "Not eklendi", tone: "success" });
      setNoteFor(null);
      setNote("");
      onChanged?.();
      return;
    }
    router.push(`/customers/${noteFor.customer_id}`);
  }

  if (top.length === 0) {
    return (
      <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-6">
        <h2 className="font-serif text-2xl text-foreground">Bugün kimi aramalıyım?</h2>
        <p className="mt-2 text-sm text-muted">Öncelikli arama listesi boş — açık bakiyeli müşteri yok.</p>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Kritik aksiyonlar</p>
          <h2 className="font-serif text-2xl tracking-tight text-foreground">Bugün kimi aramalıyım?</h2>
          <p className="mt-1 text-sm text-muted">İlk 5 öncelikli müşteri — kaydırmadan görünür</p>
        </div>
        <Link href="/collections" className="text-sm font-medium text-primary hover:underline">
          Tüm tahsilat →
        </Link>
      </div>

      {/* Desktop table */}
      <div className="hidden overflow-hidden rounded-[var(--radius-lg)] border border-border-default md:block">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-surface-secondary text-xs uppercase tracking-wide text-subtle">
            <tr>
              <th className="px-4 py-3 font-semibold">Müşteri</th>
              <th className="px-4 py-3 font-semibold">Gecikmiş</th>
              <th className="px-4 py-3 font-semibold">Gün</th>
              <th className="px-4 py-3 font-semibold">Risk</th>
              <th className="px-4 py-3 font-semibold">Son görüşme</th>
              <th className="px-4 py-3 font-semibold">Ödeme sözü</th>
              <th className="px-4 py-3 font-semibold">Öneri</th>
              <th className="px-4 py-3 font-semibold">Aksiyon</th>
            </tr>
          </thead>
          <tbody>
            {top.map((row) => (
              <CallTableRow
                key={row.customer_id}
                row={row}
                currency={currency}
                busy={busyId === row.customer_id}
                onNote={() => setNoteFor(row)}
                onDefer={() => void deferTask(row)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="grid gap-3 md:hidden">
        {top.map((row) => (
          <CallCard
            key={row.customer_id}
            row={row}
            currency={currency}
            busy={busyId === row.customer_id}
            onNote={() => setNoteFor(row)}
            onDefer={() => void deferTask(row)}
          />
        ))}
      </div>

      {rest.length > 0 ? (
        <details className="rounded-[var(--radius-md)] border border-border-default bg-surface-secondary px-4 py-3 text-sm">
          <summary className="cursor-pointer font-medium text-foreground">
            +{rest.length} müşteri daha
          </summary>
          <ul className="mt-3 space-y-2">
            {rest.map((row) => (
              <li key={row.customer_id} className="flex justify-between gap-2">
                <Link href={`/customers/${row.customer_id}`} className="text-primary hover:underline">
                  {row.customer_name}
                </Link>
                <span className="text-muted">{formatMoney(row.overdue_balance, currency)}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {noteFor ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-surface-inverse/40 p-4 sm:items-center">
          <div className="w-full max-w-md rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 shadow-[var(--shadow-lg)]">
            <h3 className="font-semibold text-foreground">Not ekle — {noteFor.customer_name}</h3>
            <Input
              className="mt-3"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Görüşme notu"
            />
            <div className="mt-3 flex gap-2">
              <Button type="button" onClick={() => void saveNote()} disabled={!note.trim()}>
                Kaydet
              </Button>
              <Button type="button" variant="secondary" onClick={() => setNoteFor(null)}>
                Vazgeç
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ActionButtons({
  row,
  busy,
  onNote,
  onDefer,
  compact,
}: {
  row: CallListRow;
  busy?: boolean;
  onNote: () => void;
  onDefer: () => void;
  compact?: boolean;
}) {
  const tel = row.customer_phone?.replace(/\s/g, "");
  return (
    <div className={cn("flex flex-wrap gap-1.5", compact && "justify-end")}>
      {tel ? (
        <a
          href={`tel:${tel}`}
          className="inline-flex h-8 items-center rounded-[var(--radius-md)] bg-primary px-2.5 text-xs font-semibold text-primary-foreground"
        >
          Ara
        </a>
      ) : (
        <Link
          href={`/collections?customer=${row.customer_id}`}
          className="inline-flex h-8 items-center rounded-[var(--radius-md)] bg-primary px-2.5 text-xs font-semibold text-primary-foreground"
        >
          Ara
        </Link>
      )}
      <button
        type="button"
        onClick={onNote}
        className="inline-flex h-8 items-center rounded-[var(--radius-md)] border border-border-default px-2.5 text-xs font-semibold"
      >
        Not
      </button>
      {row.open_task_id ? (
        <Link
          href={`/collections?task=${row.open_task_id}&complete=1`}
          className="inline-flex h-8 items-center rounded-[var(--radius-md)] border border-border-default px-2.5 text-xs font-semibold"
        >
          Tamamla
        </Link>
      ) : null}
      <Link
        href={`/promises?create=1&customer=${row.customer_id}`}
        className="inline-flex h-8 items-center rounded-[var(--radius-md)] border border-border-default px-2.5 text-xs font-semibold"
      >
        Söz
      </Link>
      <button
        type="button"
        disabled={busy}
        onClick={onDefer}
        className="inline-flex h-8 items-center rounded-[var(--radius-md)] border border-border-default px-2.5 text-xs font-semibold disabled:opacity-50"
      >
        Ertele
      </button>
    </div>
  );
}

function CallTableRow({
  row,
  currency,
  busy,
  onNote,
  onDefer,
}: {
  row: CallListRow;
  currency: string;
  busy?: boolean;
  onNote: () => void;
  onDefer: () => void;
}) {
  const risk = row.risk_status as RiskStatus;
  return (
    <tr className="border-t border-border-default align-top">
      <td className="px-4 py-3">
        <Link href={`/customers/${row.customer_id}`} className="font-semibold text-foreground hover:text-primary">
          {row.customer_name}
        </Link>
        <p className="mt-0.5 text-xs text-muted">{row.priority_reason || "Öncelikli tahsilat"}</p>
      </td>
      <td className="px-4 py-3">
        <Money value={row.overdue_balance} currency={currency} size="table" />
      </td>
      <td className="px-4 py-3 text-muted">
        {row.oldest_overdue_days == null ? "—" : `${row.oldest_overdue_days}g`}
      </td>
      <td className="px-4 py-3">
        <Badge tone={riskTone(row.risk_status)}>{RISK_LABELS[risk] ?? row.risk_status}</Badge>
      </td>
      <td className="px-4 py-3 text-muted">
        {row.last_contact_at ? formatDate(row.last_contact_at.slice(0, 10)) : "—"}
      </td>
      <td className="px-4 py-3 text-muted">
        {row.payment_promise
          ? `${formatMoney(row.payment_promise.amount, currency)} · ${formatDate(row.payment_promise.promised_date)}`
          : "—"}
      </td>
      <td className="px-4 py-3 text-xs font-medium text-primary">{row.suggested_action || "Ara"}</td>
      <td className="px-4 py-3">
        <ActionButtons row={row} busy={busy} onNote={onNote} onDefer={onDefer} compact />
      </td>
    </tr>
  );
}

function CallCard({
  row,
  currency,
  busy,
  onNote,
  onDefer,
}: {
  row: CallListRow;
  currency: string;
  busy?: boolean;
  onNote: () => void;
  onDefer: () => void;
}) {
  const risk = row.risk_status as RiskStatus;
  return (
    <article className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link href={`/customers/${row.customer_id}`} className="font-semibold text-foreground">
            {row.customer_name}
          </Link>
          <p className="mt-1 text-xs text-muted">{row.priority_reason}</p>
        </div>
        <Badge tone={riskTone(row.risk_status)}>{RISK_LABELS[risk] ?? row.risk_status}</Badge>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-subtle">Gecikmiş</dt>
          <dd className="font-semibold">
            <Money value={row.overdue_balance} currency={currency} size="table" />
          </dd>
        </div>
        <div>
          <dt className="text-subtle">Gecikme</dt>
          <dd className="font-semibold">
            {row.oldest_overdue_days == null ? "—" : `${row.oldest_overdue_days} gün`}
          </dd>
        </div>
        <div>
          <dt className="text-subtle">Son görüşme</dt>
          <dd>{row.last_contact_at ? formatDate(row.last_contact_at.slice(0, 10)) : "—"}</dd>
        </div>
        <div>
          <dt className="text-subtle">Ödeme sözü</dt>
          <dd>
            {row.payment_promise ? formatMoney(row.payment_promise.amount, currency) : "—"}
          </dd>
        </div>
      </dl>
      <p className="mt-2 text-xs font-medium text-primary">{row.suggested_action}</p>
      <div className="mt-3">
        <ActionButtons row={row} busy={busy} onNote={onNote} onDefer={onDefer} />
      </div>
    </article>
  );
}
