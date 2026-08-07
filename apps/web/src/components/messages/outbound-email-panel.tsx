"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import {
  approveOutboundEmail,
  createOutboundEmail,
  listOutboundEmails,
  previewOutboundEmail,
} from "@/lib/messages/api";
import {
  EMAIL_STATUS_LABELS,
  type MessageTemplate,
  type OutboundEmail,
  type OutboundEmailPreview,
} from "@/lib/messages/types";

export function OutboundEmailPanel({
  customerId,
  invoiceId,
  templates,
}: {
  customerId: number | null;
  invoiceId: number | null;
  templates: MessageTemplate[];
}) {
  const { toast } = useToast();
  const emailTemplates = templates.filter((t) => t.channel === "EMAIL");
  const [templateId, setTemplateId] = useState<number | null>(emailTemplates[0]?.id ?? null);
  const [draft, setDraft] = useState<OutboundEmail | null>(null);
  const [preview, setPreview] = useState<OutboundEmailPreview | null>(null);
  const [recent, setRecent] = useState<OutboundEmail[]>([]);
  const [busy, setBusy] = useState(false);

  const refreshRecent = useCallback(async () => {
    if (!customerId) {
      setRecent([]);
      return;
    }
    const result = await listOutboundEmails({ customer_id: customerId });
    if (result.ok) setRecent(result.data.results);
  }, [customerId]);

  useEffect(() => {
    void refreshRecent();
  }, [refreshRecent]);

  useEffect(() => {
    if (!templateId && emailTemplates[0]) setTemplateId(emailTemplates[0].id);
  }, [emailTemplates, templateId]);

  const onCreatePreview = async () => {
    if (!customerId || !templateId) return;
    setBusy(true);
    const created = await createOutboundEmail({
      customer_id: customerId,
      template_id: templateId,
      invoice_id: invoiceId,
      require_approval: true,
    });
    if (!created.ok) {
      setBusy(false);
      toast({ title: created.error.title, description: created.error.message, tone: "error" });
      return;
    }
    setDraft(created.data);
    const prev = await previewOutboundEmail(created.data.id);
    setBusy(false);
    if (prev.ok) setPreview(prev.data);
    toast({ title: "Ön izleme hazır", description: "Gönderim için onay gerekli.", tone: "success" });
  };

  const onApproveSend = async () => {
    if (!draft) return;
    setBusy(true);
    const result = await approveOutboundEmail(draft.id, {
      confirmed: true,
      queue_send: true,
    });
    setBusy(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    setDraft(result.data);
    setPreview(null);
    toast({
      title: "E-posta onaylandı",
      description: `Durum: ${EMAIL_STATUS_LABELS[result.data.status]}`,
      tone: "success",
    });
    void refreshRecent();
  };

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">E-posta gönderimi</h2>
        <p className="mt-1 text-xs text-slate-500">
          Şablon → ön izleme → kullanıcı onayı → gönderim. Açılma, tıklama ve bounce izlenir.
        </p>
      </div>

      <label className="block text-sm">
        <span className="mb-1 block text-slate-500">E-posta şablonu</span>
        <select
          className="h-10 w-full rounded-lg border border-slate-300 px-3"
          value={templateId ?? ""}
          onChange={(e) => setTemplateId(e.target.value ? Number(e.target.value) : null)}
          disabled={!customerId}
        >
          <option value="">Seçin</option>
          {emailTemplates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </label>

      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => void onCreatePreview()}
          loading={busy}
          disabled={!customerId || !templateId}
        >
          Ön izleme oluştur
        </Button>
        <Button
          variant="secondary"
          onClick={() => void onApproveSend()}
          loading={busy}
          disabled={!draft || draft.status !== "PENDING_APPROVAL"}
        >
          Onayla ve gönder
        </Button>
      </div>

      {preview ? (
        <div className="rounded-lg border border-amber-100 bg-amber-50 p-3 text-sm">
          <p className="text-xs text-amber-800">
            Bağlayıcı gönderim değildir — onayınız olmadan iletilmez.
          </p>
          <p className="mt-2">
            <span className="text-slate-500">Kime: </span>
            {preview.to_email}
          </p>
          <p>
            <span className="text-slate-500">Konu: </span>
            {preview.subject}
          </p>
          <pre className="mt-2 whitespace-pre-wrap font-sans text-slate-800">{preview.body_text}</pre>
        </div>
      ) : null}

      {recent.length > 0 ? (
        <div>
          <h3 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Son gönderimler
          </h3>
          <ul className="mt-2 space-y-1 text-sm text-slate-700">
            {recent.slice(0, 5).map((e) => (
              <li key={e.id} className="flex flex-wrap justify-between gap-2 border-b border-slate-100 py-1">
                <span>
                  {e.subject} · {e.to_email}
                </span>
                <span className="text-xs text-slate-500">
                  {EMAIL_STATUS_LABELS[e.status]}
                  {e.open_count ? ` · ${e.open_count} açılma` : ""}
                  {e.click_count ? ` · ${e.click_count} tık` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
