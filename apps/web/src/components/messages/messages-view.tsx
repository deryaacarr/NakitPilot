"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import { listCustomers } from "@/lib/customers/api";
import { copyToClipboard } from "@/lib/customers/format";
import type { Customer } from "@/lib/customers/types";
import { listInvoices } from "@/lib/invoices/api";
import type { Invoice } from "@/lib/invoices/types";
import {
  copyMessageTemplate,
  generateMessage,
  listMessageTemplates,
  listMessageTones,
  previewMessageTemplate,
} from "@/lib/messages/api";
import { OutboundEmailPanel } from "@/components/messages/outbound-email-panel";
import {
  CHANNEL_LABELS,
  DEFAULT_TONES,
  TEMPLATE_VARIABLES,
  type GeneratedMessage,
  type MessageChannel,
  type MessagePreview,
  type MessageTemplate,
  type MessageToneOption,
  type MessageToneValue,
} from "@/lib/messages/types";
import type { AppError } from "@/lib/errors";
import { cn } from "@/lib/cn";

type Mode = "templates" | "assistant";

export function MessagesView() {
  const { toast } = useToast();
  const [mode, setMode] = useState<Mode>("assistant");
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [tones, setTones] = useState<MessageToneOption[]>(DEFAULT_TONES);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [tone, setTone] = useState<MessageToneValue>("PROFESYONEL");
  const [customerId, setCustomerId] = useState<number | null>(null);
  const [invoiceId, setInvoiceId] = useState<number | null>(null);
  const [preview, setPreview] = useState<MessagePreview | null>(null);
  const [generated, setGenerated] = useState<GeneratedMessage | null>(null);
  const [createActivity, setCreateActivity] = useState(true);
  const [loading, setLoading] = useState(true);
  const [previewing, setPreviewing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [copying, setCopying] = useState(false);
  const [error, setError] = useState<AppError | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [tplRes, custRes, toneRes] = await Promise.all([
      listMessageTemplates(),
      listCustomers({ page_size: 100, is_active: "true" }),
      listMessageTones(),
    ]);
    setLoading(false);
    if (!tplRes.ok) {
      setError(tplRes.error);
      return;
    }
    if (!custRes.ok) {
      setError(custRes.error);
      return;
    }
    setError(null);
    const list = Array.isArray(tplRes.data) ? tplRes.data : [];
    setTemplates(list);
    setTemplateId((current) => current ?? list[0]?.id ?? null);
    setCustomers(custRes.data.results);
    if (toneRes.ok && toneRes.data.tones?.length) {
      setTones(toneRes.data.tones);
      setTone((current) => {
        const values = toneRes.data.tones.map((t) => t.value);
        return values.includes(current) ? current : toneRes.data.tones[0].value;
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!customerId) {
      setInvoices([]);
      setInvoiceId(null);
      return;
    }
    let cancelled = false;
    void listInvoices({ customer: customerId, page_size: 50 }).then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setInvoices(result.data.results);
        setInvoiceId(result.data.results[0]?.id ?? null);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  useEffect(() => {
    if (mode !== "templates" || !templateId || !customerId) {
      if (mode !== "templates") setPreview(null);
      return;
    }
    let cancelled = false;
    setPreviewing(true);
    void previewMessageTemplate(templateId, {
      customer_id: customerId,
      invoice_id: invoiceId,
    }).then((result) => {
      if (cancelled) return;
      setPreviewing(false);
      if (result.ok) setPreview(result.data);
      else setPreview(null);
    });
    return () => {
      cancelled = true;
    };
  }, [mode, templateId, customerId, invoiceId]);

  useEffect(() => {
    if (mode !== "assistant" || !customerId || !tone) {
      if (mode !== "assistant") setGenerated(null);
      return;
    }
    let cancelled = false;
    setGenerating(true);
    void generateMessage({
      customer_id: customerId,
      tone,
      invoice_id: invoiceId,
    }).then((result) => {
      if (cancelled) return;
      setGenerating(false);
      if (result.ok) setGenerated(result.data);
      else setGenerated(null);
    });
    return () => {
      cancelled = true;
    };
  }, [mode, customerId, invoiceId, tone]);

  const onCopyTemplate = async () => {
    if (!templateId || !customerId || !preview) return;
    const text =
      preview.subject && preview.channel === "EMAIL"
        ? `Konu: ${preview.subject}\n\n${preview.body}`
        : preview.body;
    const ok = await copyToClipboard(text);
    if (!ok) {
      toast({ title: "Kopyalama başarısız", tone: "error" });
      return;
    }
    setCopying(true);
    const result = await copyMessageTemplate(templateId, {
      customer_id: customerId,
      invoice_id: invoiceId,
      create_activity: createActivity,
      body: preview.body,
      subject: preview.subject,
    });
    setCopying(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    toast({
      title: "Mesaj kopyalandı",
      description: createActivity
        ? "İsteğe bağlı aktivite kaydı oluşturuldu (otomatik gönderim yok)."
        : undefined,
      tone: "success",
    });
  };

  const onCopyGenerated = async () => {
    if (!generated) return;
    const text = generated.subject
      ? `Konu: ${generated.subject}\n\n${generated.body}`
      : generated.body;
    const ok = await copyToClipboard(text);
    if (!ok) {
      toast({ title: "Kopyalama başarısız", tone: "error" });
      return;
    }
    toast({
      title: "Mesaj kopyalandı",
      description: "Otomatik gönderim yok — metin panoya alındı.",
      tone: "success",
    });
  };

  if (loading) return <LoadingSkeleton lines={10} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;

  const selected = templates.find((t) => t.id === templateId) ?? null;
  const source = generated?.source_fields;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Mesajlar</h1>
        <p className="text-sm text-slate-600">
          Ton asistanı veya şablon ile metin üretin; e-posta gönderimi ön izleme ve kullanıcı onayı
          ister. Tutar ve fatura alanları veritabanından doldurulur.
        </p>
      </header>

      <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1 text-sm">
        <button
          type="button"
          onClick={() => setMode("assistant")}
          className={cn(
            "rounded-md px-3 py-1.5 transition",
            mode === "assistant" ? "bg-brand/10 font-medium text-brand" : "text-slate-600",
          )}
        >
          Mesaj üretme asistanı
        </button>
        <button
          type="button"
          onClick={() => setMode("templates")}
          className={cn(
            "rounded-md px-3 py-1.5 transition",
            mode === "templates" ? "bg-brand/10 font-medium text-brand" : "text-slate-600",
          )}
        >
          Şablonlar
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
          {mode === "assistant" ? (
            <>
              <h2 className="px-1 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Ton
              </h2>
              <ul className="space-y-1">
                {tones.map((t) => (
                  <li key={t.value}>
                    <button
                      type="button"
                      onClick={() => setTone(t.value)}
                      className={cn(
                        "w-full rounded-lg px-3 py-2 text-left text-sm transition",
                        tone === t.value
                          ? "bg-brand/10 text-brand"
                          : "text-slate-700 hover:bg-slate-50",
                      )}
                    >
                      {t.label}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="border-t border-slate-100 px-1 pt-3 text-xs text-slate-500">
                Tutar, fatura numarası, vade ve gecikme günü seçilen faturadan gelir.
              </p>
            </>
          ) : (
            <>
              <h2 className="px-1 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Şablonlar
              </h2>
              {templates.length === 0 ? (
                <EmptyState title="Şablon yok" description="Varsayılan şablonlar oluşturulamadı." />
              ) : (
                <ul className="space-y-1">
                  {templates.map((tpl) => (
                    <li key={tpl.id}>
                      <button
                        type="button"
                        onClick={() => setTemplateId(tpl.id)}
                        className={cn(
                          "w-full rounded-lg px-3 py-2 text-left text-sm transition",
                          templateId === tpl.id
                            ? "bg-brand/10 text-brand"
                            : "text-slate-700 hover:bg-slate-50",
                        )}
                      >
                        <span className="font-medium">{tpl.name}</span>
                        <span className="mt-0.5 block text-xs text-slate-500">
                          {CHANNEL_LABELS[tpl.channel as MessageChannel]}
                          {tpl.is_default ? " · varsayılan" : ""}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="border-t border-slate-100 pt-3">
                <p className="mb-1 text-xs font-medium text-slate-500">Değişkenler</p>
                <ul className="space-y-0.5 text-xs text-slate-600">
                  {TEMPLATE_VARIABLES.map((v) => (
                    <li key={v}>
                      <code className="rounded bg-slate-100 px-1">{`{{${v}}}`}</code>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </aside>

        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block text-slate-500">Müşteri</span>
              <select
                className="h-10 w-full rounded-lg border border-slate-300 px-3"
                value={customerId ?? ""}
                onChange={(e) => setCustomerId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Seçin</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-500">Fatura (opsiyonel)</span>
              <select
                className="h-10 w-full rounded-lg border border-slate-300 px-3"
                value={invoiceId ?? ""}
                onChange={(e) => setInvoiceId(e.target.value ? Number(e.target.value) : null)}
                disabled={!customerId}
              >
                <option value="">Otomatik (en eski açık)</option>
                {invoices.map((inv) => (
                  <option key={inv.id} value={inv.id}>
                    {inv.number}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {mode === "templates" && selected ? (
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <Badge tone="neutral">{CHANNEL_LABELS[selected.channel]}</Badge>
              <span>{selected.name}</span>
            </div>
          ) : null}

          {mode === "assistant" && source && customerId ? (
            <div className="grid gap-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:grid-cols-4">
              <div>
                <span className="block text-slate-400">Tutar</span>
                <span className="font-medium text-slate-800">{source.amount || "—"}</span>
              </div>
              <div>
                <span className="block text-slate-400">Fatura no</span>
                <span className="font-medium text-slate-800">
                  {source.invoice_number || "—"}
                </span>
              </div>
              <div>
                <span className="block text-slate-400">Vade</span>
                <span className="font-medium text-slate-800">{source.due_date || "—"}</span>
              </div>
              <div>
                <span className="block text-slate-400">Gecikme</span>
                <span className="font-medium text-slate-800">
                  {source.overdue_days ? `${source.overdue_days} gün` : "—"}
                </span>
              </div>
            </div>
          ) : null}

          <div className="rounded-lg border border-slate-100 bg-slate-50 p-4">
            <h3 className="mb-2 text-sm font-semibold text-slate-900">
              {mode === "assistant" ? "Üretilen mesaj" : "Ön izleme"}
            </h3>
            {!customerId ? (
              <p className="text-sm text-slate-500">Mesaj için müşteri seçin.</p>
            ) : mode === "assistant" ? (
              generating ? (
                <LoadingSkeleton lines={4} />
              ) : generated ? (
                <div className="space-y-3">
                  {generated.subject ? (
                    <p className="text-sm">
                      <span className="text-slate-500">Konu: </span>
                      <span className="font-medium text-slate-900">{generated.subject}</span>
                    </p>
                  ) : null}
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-slate-800">
                    {generated.body}
                  </pre>
                </div>
              ) : (
                <p className="text-sm text-slate-500">Mesaj üretilemedi.</p>
              )
            ) : previewing ? (
              <LoadingSkeleton lines={4} />
            ) : preview ? (
              <div className="space-y-3">
                {preview.subject ? (
                  <p className="text-sm">
                    <span className="text-slate-500">Konu: </span>
                    <span className="font-medium text-slate-900">{preview.subject}</span>
                  </p>
                ) : null}
                <pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-slate-800">
                  {preview.body}
                </pre>
              </div>
            ) : (
              <p className="text-sm text-slate-500">Ön izleme üretilemedi.</p>
            )}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {mode === "templates" ? (
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={createActivity}
                  onChange={(e) => setCreateActivity(e.target.checked)}
                  className="size-4 rounded border-slate-300"
                />
                Kopyalınca müşteri aktivitesi oluştur
              </label>
            ) : (
              <span className="text-xs text-slate-500">Alanlar veritabanından doldurulur.</span>
            )}
            <Button
              onClick={() =>
                void (mode === "assistant" ? onCopyGenerated() : onCopyTemplate())
              }
              loading={copying}
              disabled={mode === "assistant" ? !generated : !preview}
            >
              Mesajı kopyala
            </Button>
          </div>
        </section>
      </div>

      <OutboundEmailPanel
        customerId={customerId}
        invoiceId={invoiceId}
        templates={templates}
      />
    </div>
  );
}
