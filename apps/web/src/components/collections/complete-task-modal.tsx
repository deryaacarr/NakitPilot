"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { completeCollectionTask } from "@/lib/collections/api";
import {
  OUTCOME_LABELS,
  type CallOutcome,
  type CollectionTask,
} from "@/lib/collections/types";

export function validateCompleteTaskNotes(notes: string): boolean {
  return notes.trim().length > 0;
}

type OutcomeFields = {
  showPromise: boolean;
  showFollowUp: boolean;
  followUpRequired: boolean;
  promiseRequired: boolean;
  noteHint: string;
};

function fieldsForOutcome(outcome: CallOutcome): OutcomeFields {
  switch (outcome) {
    case "PROMISE_GIVEN":
      return {
        showPromise: true,
        showFollowUp: true,
        followUpRequired: false,
        promiseRequired: true,
        noteHint: "Söz tutarı ve tarihiyle birlikte kısa not yazın.",
      };
    case "CALLBACK":
      return {
        showPromise: false,
        showFollowUp: true,
        followUpRequired: true,
        promiseRequired: false,
        noteHint: "Tekrar arama nedenini kısaca yazın.",
      };
    case "NOT_REACHED":
      return {
        showPromise: false,
        showFollowUp: true,
        followUpRequired: false,
        promiseRequired: false,
        noteHint: "Ulaşılamama detayı (mesai dışı, meşgul vb.).",
      };
    case "PAYMENT_MADE":
      return {
        showPromise: false,
        showFollowUp: false,
        followUpRequired: false,
        promiseRequired: false,
        noteHint: "Ödeme tutarı / kanalı kısaca.",
      };
    case "DISPUTED":
      return {
        showPromise: false,
        showFollowUp: true,
        followUpRequired: false,
        promiseRequired: false,
        noteHint: "İtiraz konusunu kısaca yazın.",
      };
    case "WRONG_PERSON":
      return {
        showPromise: false,
        showFollowUp: false,
        followUpRequired: false,
        promiseRequired: false,
        noteHint: "Doğru kişi bilgisi varsa ekleyin.",
      };
    default:
      return {
        showPromise: false,
        showFollowUp: true,
        followUpRequired: false,
        promiseRequired: false,
        noteHint: "Görüşme özeti — kısa tutun.",
      };
  }
}

function tomorrowIso() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
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
  const [callbackDate, setCallbackDate] = useState("");
  const [promiseDate, setPromiseDate] = useState("");
  const [promiseAmount, setPromiseAmount] = useState("");

  const fields = useMemo(() => fieldsForOutcome(outcome), [outcome]);

  const onOutcomeChange = (next: CallOutcome) => {
    setOutcome(next);
    const cfg = fieldsForOutcome(next);
    if (cfg.followUpRequired) {
      setCreateFollowUp(true);
      if (!callbackDate) setCallbackDate(tomorrowIso());
    } else if (next === "PAYMENT_MADE" || next === "WRONG_PERSON") {
      setCreateFollowUp(false);
    }
    if (cfg.promiseRequired && !promiseDate) {
      setPromiseDate(tomorrowIso());
    }
  };

  const submit = async () => {
    if (!validateCompleteTaskNotes(notes)) {
      toast({ title: "Görüşme notu zorunlu", tone: "warning" });
      return;
    }
    const wantPromise = fields.showPromise && fields.promiseRequired;
    const wantFollowUp = fields.showFollowUp && (fields.followUpRequired || createFollowUp);

    if (wantPromise && (!promiseAmount.trim() || !promiseDate)) {
      toast({ title: "Ödeme sözü için tutar ve tarih gerekli", tone: "warning" });
      return;
    }
    if (wantFollowUp && !callbackDate) {
      toast({ title: "Takip tarihi gerekli", tone: "warning" });
      return;
    }

    setBusy(true);
    const result = await completeCollectionTask(task.id, {
      outcome,
      outcome_notes: notes,
      create_follow_up: wantFollowUp,
      promise_given: wantPromise,
      callback_date: wantFollowUp ? callbackDate || null : null,
      promise_date: wantPromise ? promiseDate || null : null,
      promise_amount: wantPromise ? promiseAmount || null : null,
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
      description={`${task.customer_name} · hızlı kayıt`}
      size="md"
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Vazgeç
          </Button>
          <Button type="button" loading={busy} onClick={() => void submit()}>
            Kaydet
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <Select
          name="outcome"
          label="Görüşme sonucu *"
          options={Object.entries(OUTCOME_LABELS).map(([value, label]) => ({ value, label }))}
          value={outcome}
          onChange={(event) => onOutcomeChange(event.target.value as CallOutcome)}
        />

        <Textarea
          name="outcome_notes"
          label="Not *"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          rows={2}
          placeholder={fields.noteHint}
        />

        {fields.showPromise ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              name="promise_amount"
              label="Söz tutarı *"
              value={promiseAmount}
              onChange={(event) => setPromiseAmount(event.target.value)}
              placeholder="1500.00"
            />
            <Input
              name="promise_date"
              label="Söz tarihi *"
              type="date"
              value={promiseDate}
              onChange={(event) => setPromiseDate(event.target.value)}
            />
          </div>
        ) : null}

        {fields.showFollowUp ? (
          <div className="space-y-3">
            {!fields.followUpRequired ? (
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={createFollowUp}
                  onChange={(event) => {
                    setCreateFollowUp(event.target.checked);
                    if (event.target.checked && !callbackDate) setCallbackDate(tomorrowIso());
                  }}
                />
                Yeni görev oluştur
              </label>
            ) : (
              <p className="text-xs font-medium text-muted">Takip görevi otomatik oluşturulacak.</p>
            )}
            {(fields.followUpRequired || createFollowUp) && (
              <Input
                name="callback_date"
                label="Takip tarihi *"
                type="date"
                value={callbackDate}
                onChange={(event) => setCallbackDate(event.target.value)}
              />
            )}
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
