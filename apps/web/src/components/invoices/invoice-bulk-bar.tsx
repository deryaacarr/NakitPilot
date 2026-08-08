"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { bulkInvoiceAction, type BulkAction } from "@/lib/invoices/bulk";

export function InvoiceBulkBar({
  selectedIds,
  onDone,
  onClear,
  assignees,
}: {
  selectedIds: number[];
  onDone: () => void;
  onClear: () => void;
  assignees: Array<{ id: number; label: string }>;
}) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const [confirmAction, setConfirmAction] = useState<BulkAction | null>(null);
  const [assignee, setAssignee] = useState("");
  const [tags, setTags] = useState("");

  if (selectedIds.length === 0) return null;

  async function run(action: BulkAction, extra: Record<string, unknown> = {}) {
    setBusy(true);
    const res = await bulkInvoiceAction(action, selectedIds, extra);
    setBusy(false);
    setConfirmAction(null);
    if (!res.ok) {
      toast({ title: "Toplu işlem başarısız", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "İşlem tamamlandı", description: res.data.summary, tone: "success" });
    if (res.data.csv && res.data.filename) {
      const blob = new Blob([res.data.csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.data.filename;
      a.click();
      URL.revokeObjectURL(url);
    }
    if (res.data.href) {
      window.location.href = res.data.href;
      return;
    }
    onDone();
  }

  function request(action: BulkAction) {
    if (action === "change_assignee" || action === "add_tags" || action === "recalculate_risk") {
      setConfirmAction(action);
      return;
    }
    void run(action);
  }

  return (
    <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 rounded-[var(--radius-lg)] border border-primary/30 bg-primary/10 px-3 py-2">
      <p className="text-sm font-semibold text-foreground">{selectedIds.length} seçili</p>
      <Button size="sm" disabled={busy} onClick={() => request("assign_tasks")}>
        Görev ata
      </Button>
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => request("change_assignee")}>
        Sorumlu değiştir
      </Button>
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => request("add_tags")}>
        Etiket ekle
      </Button>
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => request("prepare_message")}>
        Mesaj hazırla
      </Button>
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => request("export_excel")}>
        Excel dışa aktar
      </Button>
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => request("recalculate_risk")}>
        Risk hesapla
      </Button>
      <Button size="sm" variant="ghost" disabled={busy} onClick={onClear}>
        Seçimi temizle
      </Button>

      {confirmAction ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-inverse/40 p-4">
          <div className="w-full max-w-md space-y-3 rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4 shadow-[var(--shadow-lg)]">
            <h3 className="font-semibold text-foreground">
              {confirmAction === "recalculate_risk"
                ? "Risk yeniden hesaplansın mı?"
                : confirmAction === "change_assignee"
                  ? "Sorumlu değiştir"
                  : "Etiket ekle"}
            </h3>
            <p className="text-sm text-muted">{selectedIds.length} fatura etkilenecek.</p>
            {confirmAction === "change_assignee" ? (
              <select
                className="h-10 w-full rounded-[var(--radius-md)] border border-border-default px-3 text-sm"
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
              >
                <option value="">Sorumlu seçin</option>
                {assignees.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label}
                  </option>
                ))}
              </select>
            ) : null}
            {confirmAction === "add_tags" ? (
              <Input
                label="Etiketler (virgülle)"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="öncelik, hukuki"
              />
            ) : null}
            <div className="flex gap-2">
              <Button
                size="sm"
                loading={busy}
                disabled={
                  busy ||
                  (confirmAction === "change_assignee" && !assignee) ||
                  (confirmAction === "add_tags" && !tags.trim())
                }
                onClick={() => {
                  if (confirmAction === "change_assignee") {
                    void run("change_assignee", { assigned_user: Number(assignee) });
                  } else if (confirmAction === "add_tags") {
                    void run("add_tags", {
                      tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
                    });
                  } else {
                    void run("recalculate_risk");
                  }
                }}
              >
                Onayla
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setConfirmAction(null)}>
                Vazgeç
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
