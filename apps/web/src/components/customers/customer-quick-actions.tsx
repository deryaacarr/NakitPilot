"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { addCustomerTimelineNote } from "@/lib/collections/api";
import type { Customer } from "@/lib/customers/types";
import { cn } from "@/lib/cn";

type Props = {
  customer: Customer;
  sticky?: boolean;
  onNoteAdded?: () => void;
  className?: string;
};

export function CustomerQuickActions({ customer, sticky, onNoteAdded, className }: Props) {
  const { toast } = useToast();
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const tel = customer.phone?.replace(/\s/g, "");

  async function saveNote() {
    if (!note.trim()) return;
    setSaving(true);
    const res = await addCustomerTimelineNote(customer.id, { notes: note.trim() });
    setSaving(false);
    if (!res.ok) {
      toast({ title: "Not eklenemedi", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Not eklendi", tone: "success" });
    setNote("");
    setNoteOpen(false);
    onNoteAdded?.();
  }

  const actions = (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {tel ? (
        <a
          href={`tel:${tel}`}
          className="inline-flex h-9 items-center rounded-[var(--radius-md)] bg-primary px-3 text-xs font-semibold text-primary-foreground"
        >
          Ara
        </a>
      ) : (
        <Link
          href={`/messages?customer=${customer.id}`}
          className="inline-flex h-9 items-center rounded-[var(--radius-md)] bg-primary px-3 text-xs font-semibold text-primary-foreground"
        >
          Ara
        </Link>
      )}
      <Link
        href={`/messages?customer=${customer.id}`}
        className="inline-flex h-9 items-center rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3 text-xs font-semibold"
      >
        Mesaj hazırla
      </Link>
      <Link
        href={`/collections/tasks?create=1&customer=${customer.id}`}
        className="inline-flex h-9 items-center rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3 text-xs font-semibold"
      >
        Görev oluştur
      </Link>
      <Link
        href={`/promises?create=1&customer=${customer.id}`}
        className="inline-flex h-9 items-center rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3 text-xs font-semibold"
      >
        Ödeme sözü ekle
      </Link>
      <button
        type="button"
        onClick={() => setNoteOpen(true)}
        className="inline-flex h-9 items-center rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-3 text-xs font-semibold"
      >
        Not ekle
      </button>
    </div>
  );

  return (
    <>
      {sticky ? (
        <div className="sticky bottom-3 z-30 mt-4">
          <div className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary/95 px-3 py-2 shadow-[var(--shadow-md)] backdrop-blur">
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-subtle">
              Hızlı aksiyonlar
            </p>
            {actions}
          </div>
        </div>
      ) : (
        actions
      )}

      {noteOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-surface-inverse/40 p-4 sm:items-center">
          <div className="w-full max-w-md space-y-3 rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 shadow-[var(--shadow-lg)]">
            <h3 className="font-semibold text-foreground">Not ekle — {customer.name}</h3>
            <Input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Görüşme / takip notu"
            />
            <div className="flex gap-2">
              <Button type="button" loading={saving} disabled={saving || !note.trim()} onClick={() => void saveNote()}>
                Kaydet
              </Button>
              <Button type="button" variant="secondary" onClick={() => setNoteOpen(false)}>
                Vazgeç
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
