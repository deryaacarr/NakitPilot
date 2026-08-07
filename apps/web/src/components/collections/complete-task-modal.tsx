"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  completeCollectionTask,
  confirmCollectionNotes,
  parseCollectionNotes,
  type StructuredNotesDraft,
} from "@/lib/collections/api";
import {
  OUTCOME_LABELS,
  type CallOutcome,
  type CollectionTask,
} from "@/lib/collections/types";
import { cn } from "@/lib/cn";

export function validateCompleteTaskNotes(notes: string): boolean {
  return notes.trim().length > 0;
}

export function CompleteTaskModal({
  task,
  onClose,
  onDone,
}: {
  task: CollectionTask;
  onClose: () => void;
  onDone: () => void;
}) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<CallOutcome>("REACHED");
  const [notes, setNotes] = useState("");
  const [createFollowUp, setCreateFollowUp] = useState(false);
  const [promiseGiven, setPromiseGiven] = useState(false);
  const [callbackDate, setCallbackDate] = useState("");
  const [promiseDate, setPromiseDate] = useState("");
  const [promiseAmount, setPromiseAmount] = useState("");
  const [draft, setDraft] = useState<StructuredNotesDraft | null>(null);
  const [sentiment, setSentiment] = useState("neutral");
  const [objection, setObjection] = useState("");
  const [nextActionDate, setNextActionDate] = useState("");
  const [useStructured, setUseStructured] = useState(false);

  const parseNotes = async () => {
    if (!validateCompleteTaskNotes(notes)) {
      toast({ title: "Önce görüşme notunu yazın", tone: "warning" });
      return;
    }
    setBusy(true);
    const result = await parseCollectionNotes(task.id, notes);
    setBusy(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    const d = result.data.draft;
    setDraft(d);
    setUseStructured(true);
    setSentiment(d.sentiment || "neutral");
    setObjection(d.objection || "");
    setNextActionDate(d.next_action_date || "");
    if (d.promised_amount) {
      setPromiseGiven(true);
      setPromiseAmount(d.promised_amount);
    }
    if (d.promised_date) {
      setPromiseGiven(true);
      setPromiseDate(d.promised_date);
    }
    if (d.next_action_date) {
      setCreateFollowUp(true);
      setCallbackDate(d.next_action_date);
    }
    if (d.objection && !d.promised_amount) {
      setOutcome("DISPUTED");
    } else if (d.promised_amount) {
      setOutcome("PROMISE_GIVEN");
    }
    toast({ title: "Not yapılandırıldı — onaylayıp kaydedin", tone: "success" });
  };

  const submit = async () => {
    if (!validateCompleteTaskNotes(notes)) {
      toast({ title: "Görüşme notu zorunlu", tone: "warning" });
      return;
    }
    setBusy(true);

    if (useStructured && draft) {
      const result = await confirmCollectionNotes(task.id, {
        raw_notes: notes,
        promised_amount: promiseGiven ? promiseAmount || null : null,
        promised_date: promiseGiven ? promiseDate || null : null,
        next_action_date: nextActionDate || callbackDate || null,
        sentiment,
        objection: objection || null,
        complete_task: true,
        confirmed: true,
      });
      setBusy(false);
      if (!result.ok) {
        toast({ title: result.error.title, description: result.error.message, tone: "error" });
        return;
      }
      onDone();
      return;
    }

    const result = await completeCollectionTask(task.id, {
      outcome,
      outcome_notes: notes,
      create_follow_up: createFollowUp,
      promise_given: promiseGiven,
      callback_date: createFollowUp ? callbackDate || null : null,
      promise_date: promiseGiven ? promiseDate || null : null,
      promise_amount: promiseGiven ? promiseAmount || null : null,
    });
    setBusy(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    onDone();
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Görevi tamamla"
      description={task.customer_name}
      size="lg"
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Vazgeç
          </Button>
          <Button type="button" variant="outline" loading={busy} onClick={() => void parseNotes()}>
            Notu yapılandır
          </Button>
          <Button type="button" loading={busy} onClick={() => void submit()}>
            {useStructured ? "Onayla ve kaydet" : "Kaydet"}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <Select
          label="Görüşme sonucu *"
          options={Object.entries(OUTCOME_LABELS).map(([value, label]) => ({ value, label }))}
          value={outcome}
          onChange={(event) => setOutcome(event.target.value as CallOutcome)}
        />
        <Textarea
          name="outcome_notes"
          label="Görüşme notu *"
          value={notes}
          onChange={(event) => {
            setNotes(event.target.value);
            setUseStructured(false);
            setDraft(null);
          }}
          rows={4}
          placeholder="Örn: Müşteri cuma günü 80 bin ödeyeceğini söyledi, kalanını ay sonuna bırakmak istiyor."
        />

        {useStructured && draft ? (
          <div className="space-y-3 rounded-xl border border-teal-100 bg-teal-50/40 p-3">
            <p className="text-xs font-semibold tracking-wide text-teal-800 uppercase">
              Yapılandırılmış taslak (kayıt için onay gerekli)
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="Söz tutarı"
                value={promiseAmount}
                onChange={(event) => setPromiseAmount(event.target.value)}
              />
              <Input
                label="Söz tarihi"
                type="date"
                value={promiseDate}
                onChange={(event) => setPromiseDate(event.target.value)}
              />
              <Input
                label="Sonraki aksiyon"
                type="date"
                value={nextActionDate}
                onChange={(event) => setNextActionDate(event.target.value)}
              />
              <Select
                label="Sentiment"
                options={[
                  { value: "positive", label: "Olumlu" },
                  { value: "neutral", label: "Nötr" },
                  { value: "negative", label: "Olumsuz" },
                ]}
                value={sentiment}
                onChange={(event) => setSentiment(event.target.value)}
              />
            </div>
            <Input
              label="İtiraz kodu"
              value={objection}
              onChange={(event) => setObjection(event.target.value)}
              placeholder="remaining_balance_deferred"
            />
          </div>
        ) : null}

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={createFollowUp}
            onChange={(event) => setCreateFollowUp(event.target.checked)}
          />
          Yeni görev oluşturulsun mu?
        </label>
        {createFollowUp ? (
          <Input
            label="Tekrar aranma tarihi *"
            type="date"
            value={callbackDate}
            onChange={(event) => setCallbackDate(event.target.value)}
          />
        ) : null}
        <label className={cn("flex items-center gap-2 text-sm text-slate-700")}>
          <input
            type="checkbox"
            checked={promiseGiven}
            onChange={(event) => setPromiseGiven(event.target.checked)}
          />
          Ödeme sözü verildi mi?
        </label>
        {promiseGiven && !useStructured ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              name="promise_date"
              label="Söz tarihi *"
              type="date"
              value={promiseDate}
              onChange={(event) => setPromiseDate(event.target.value)}
            />
            <Input
              name="promise_amount"
              label="Söz tutarı *"
              value={promiseAmount}
              onChange={(event) => setPromiseAmount(event.target.value)}
              placeholder="1500.00"
            />
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
