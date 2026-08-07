"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  getCommunicationFrequency,
  getCommunicationPreferences,
  updateCommunicationPreferences,
  type CommunicationPreference,
  type FrequencyCheck,
} from "@/lib/customers/communication";
import type { AppError } from "@/lib/errors";

type Props = { customerId: number };

export function CustomerCommunicationPanel({ customerId }: Props) {
  const { toast } = useToast();
  const [pref, setPref] = useState<CommunicationPreference | null>(null);
  const [freq, setFreq] = useState<FrequencyCheck | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<AppError | null>(null);

  const load = useCallback(async () => {
    const [p, f] = await Promise.all([
      getCommunicationPreferences(customerId),
      getCommunicationFrequency(customerId),
    ]);
    setLoading(false);
    if (!p.ok) {
      setError(p.error);
      return;
    }
    setError(null);
    setPref(p.data);
    if (f.ok) setFreq(f.data);
  }, [customerId]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = (key: keyof CommunicationPreference) => {
    if (!pref) return;
    setPref({ ...pref, [key]: !pref[key] });
  };

  const save = async () => {
    if (!pref) return;
    setSaving(true);
    const result = await updateCommunicationPreferences(customerId, {
      email_ok: pref.email_ok,
      whatsapp_ok: pref.whatsapp_ok,
      sms_ok: pref.sms_ok,
      phone_ok: pref.phone_ok,
      no_contact_permission: pref.no_contact_permission,
      contact_hours_start: pref.contact_hours_start,
      contact_hours_end: pref.contact_hours_end,
      notes: pref.notes,
    });
    setSaving(false);
    if (!result.ok) {
      toast({ title: "Kaydedilemedi", description: result.error.message, tone: "error" });
      return;
    }
    setPref(result.data);
    toast({ title: "İletişim tercihleri kaydedildi", tone: "success" });
    void load();
  };

  if (loading) return <LoadingSkeleton className="h-40" />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;
  if (!pref) return null;

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2 text-sm text-slate-800">
        <input
          type="checkbox"
          checked={pref.no_contact_permission}
          onChange={() => toggle("no_contact_permission")}
        />
        İletişim izni yok
      </label>
      <div className="grid grid-cols-2 gap-2 text-sm">
        {(
          [
            ["email_ok", "E-posta uygun"],
            ["whatsapp_ok", "WhatsApp uygun"],
            ["sms_ok", "SMS uygun"],
            ["phone_ok", "Telefon uygun"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-slate-700">
            <input
              type="checkbox"
              checked={Boolean(pref[key])}
              disabled={pref.no_contact_permission}
              onChange={() => toggle(key)}
            />
            {label}
          </label>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs text-slate-600">
          Başlangıç saati
          <Input
            type="time"
            value={(pref.contact_hours_start || "").slice(0, 5)}
            onChange={(e) =>
              setPref({
                ...pref,
                contact_hours_start: e.target.value ? `${e.target.value}:00` : null,
              })
            }
          />
        </label>
        <label className="text-xs text-slate-600">
          Bitiş saati
          <Input
            type="time"
            value={(pref.contact_hours_end || "").slice(0, 5)}
            onChange={(e) =>
              setPref({
                ...pref,
                contact_hours_end: e.target.value ? `${e.target.value}:00` : null,
              })
            }
          />
        </label>
      </div>
      <Textarea
        placeholder="Not"
        value={pref.notes || ""}
        onChange={(e) => setPref({ ...pref, notes: e.target.value })}
      />
      {freq ? (
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Sıklık: 24s otomatik {freq.auto_last_24h}/{freq.limits.max_auto_per_24h} · 7g{" "}
          {freq.messages_last_7d}/{freq.limits.max_messages_per_7d}
          {freq.open_dispute ? " · Açık itiraz var (otomasyon kapalı)" : ""}
          {!freq.allowed && freq.reason ? ` — ${freq.reason}` : ""}
        </p>
      ) : null}
      <Button type="button" onClick={() => void save()} disabled={saving}>
        {saving ? "Kaydediliyor…" : "Kaydet"}
      </Button>
    </div>
  );
}
