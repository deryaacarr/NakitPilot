"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { useToast } from "@/components/ui/toast";
import {
  approveLegalCase,
  createLegalCase,
  fetchLegalCriteria,
  generateLegalPackage,
  getLegalCase,
  handoffLegalCase,
  listLegalCases,
  updateLegalCaseStatus,
} from "@/lib/legal/api";
import { LEGAL_STATUS_LABELS, type LegalCase, type LegalCaseDetail, type LegalCriteria } from "@/lib/legal/types";
import { formatMoney } from "@/lib/customers/format";
import type { AppError } from "@/lib/errors";

const NEXT_STATUS: Record<string, string[]> = {
  PREPARING: ["HANDED_TO_LAWYER", "CLOSED"],
  HANDED_TO_LAWYER: ["NOTICE", "MEDIATION", "CLOSED"],
  NOTICE: ["MEDIATION", "LAWSUIT", "ENFORCEMENT", "COLLECTED", "CLOSED"],
  MEDIATION: ["NOTICE", "LAWSUIT", "ENFORCEMENT", "COLLECTED", "CLOSED"],
  LAWSUIT: ["ENFORCEMENT", "COLLECTED", "CLOSED"],
  ENFORCEMENT: ["COLLECTED", "CLOSED"],
  COLLECTED: ["CLOSED"],
  CLOSED: [],
};

export function LegalCasesBoard({ lawyerPortal = false }: { lawyerPortal?: boolean }) {
  const { toast } = useToast();
  const [rows, setRows] = useState<LegalCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [selected, setSelected] = useState<LegalCaseDetail | null>(null);
  const [customerId, setCustomerId] = useState("");
  const [lawyerId, setLawyerId] = useState("");
  const [criteria, setCriteria] = useState<LegalCriteria | null>(null);

  const load = useCallback(async () => {
    const result = await listLegalCases();
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError(null);
    setRows(result.data.results || []);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function openCase(id: number) {
    const result = await getLegalCase(id);
    if (!result.ok) {
      toast({ title: "Dosya açılamadı", description: result.error.message, tone: "error" });
      return;
    }
    setSelected(result.data);
  }

  if (loading) return <LoadingSkeleton lines={8} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          {lawyerPortal ? "Avukat portalı" : "Hukuki hazırlık"}
        </p>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">
          {lawyerPortal ? "Atanan dosyalar" : "Hukuki dosyalar"}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          {lawyerPortal
            ? "Yalnızca size atanan dosyaları görür; tam finans verisine erişim yoktur."
            : "Dosya hazırlama ve süreç takibi — otomatik hukuki karar vermez."}
        </p>
      </div>

      {!lawyerPortal ? (
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">Yeni dosya / kriter kontrolü</h2>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              placeholder="Müşteri ID"
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
            <Button
              variant="secondary"
              onClick={async () => {
                const id = Number(customerId);
                if (!id) return;
                const result = await fetchLegalCriteria(id);
                if (!result.ok) {
                  toast({ title: "Kriter alınamadı", tone: "error" });
                  return;
                }
                setCriteria(result.data);
              }}
            >
              Kriterleri değerlendir
            </Button>
            <Button
              onClick={async () => {
                const id = Number(customerId);
                if (!id) return;
                const result = await createLegalCase({ customer: id });
                if (!result.ok) {
                  toast({ title: "Oluşturulamadı", description: result.error.message, tone: "error" });
                  return;
                }
                toast({ title: "Dosya oluşturuldu", tone: "success" });
                setSelected(result.data);
                void load();
              }}
            >
              Dosya oluştur
            </Button>
          </div>
          {criteria ? (
            <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
              <p className="font-medium">{criteria.customer_name}</p>
              <p className="text-xs text-slate-500">{criteria.disclaimer}</p>
              <ul className="mt-2 space-y-1">
                {criteria.rules.map((r) => (
                  <li key={r.code} className="flex justify-between gap-2">
                    <span>{r.label}</span>
                    <Badge tone={r.met ? "success" : "warning"}>{r.met ? "OK" : "Eksik"}</Badge>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="space-y-3">
        {rows.length === 0 ? (
          <EmptyState title="Dosya yok" description="Henüz hukuki dosya oluşturulmadı." />
        ) : (
          rows.map((row) => (
            <button
              key={row.id}
              type="button"
              onClick={() => void openCase(row.id)}
              className="flex w-full items-start justify-between rounded-xl border border-slate-200 bg-white p-4 text-left hover:border-slate-300"
            >
              <div>
                <p className="font-semibold text-slate-900">
                  #{row.id} {row.customer_name || row.title}
                </p>
                <p className="text-xs text-slate-500">{row.title}</p>
              </div>
              <div className="text-right">
                <Badge>{LEGAL_STATUS_LABELS[row.status] || row.status}</Badge>
                <p className="mt-1 text-xs text-slate-500">{formatMoney(row.balance_at_open)}</p>
              </div>
            </button>
          ))
        )}
      </section>

      {selected ? (
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                #{selected.id} {selected.customer_name || selected.title}
              </h2>
              <p className="text-sm text-slate-600">
                {LEGAL_STATUS_LABELS[selected.status] || selected.status}
              </p>
              {selected.disclaimer ? (
                <p className="mt-1 text-xs text-slate-500">{selected.disclaimer}</p>
              ) : null}
            </div>
            <Button variant="ghost" onClick={() => setSelected(null)}>
              Kapat
            </Button>
          </div>

          {!lawyerPortal ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {!selected.manager_approved ? (
                <Button
                  size="sm"
                  onClick={async () => {
                    const result = await approveLegalCase(selected.id);
                    if (!result.ok) {
                      toast({ title: "Onay başarısız", tone: "error" });
                      return;
                    }
                    setSelected(result.data);
                    void load();
                  }}
                >
                  Yönetici onayı
                </Button>
              ) : null}
              <input
                value={lawyerId}
                onChange={(e) => setLawyerId(e.target.value)}
                placeholder="Avukat kullanıcı ID"
                className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
              />
              <Button
                size="sm"
                variant="secondary"
                onClick={async () => {
                  const id = Number(lawyerId);
                  if (!id) return;
                  const result = await handoffLegalCase(selected.id, id);
                  if (!result.ok) {
                    toast({
                      title: "Aktarım başarısız",
                      description: result.error.message,
                      tone: "error",
                    });
                    return;
                  }
                  setSelected(result.data);
                  void load();
                }}
              >
                Avukata aktar
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={async () => {
                  const result = await generateLegalPackage(selected.id);
                  if (!result.ok) {
                    toast({ title: "Paket üretilemedi", tone: "error" });
                    return;
                  }
                  toast({ title: "Hazırlık paketi üretildi", tone: "success" });
                  void openCase(selected.id);
                }}
              >
                PDF/ZIP paket
              </Button>
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-2">
            {(NEXT_STATUS[selected.status] || []).map((status) => (
              <Button
                key={status}
                size="sm"
                variant="outline"
                onClick={async () => {
                  const result = await updateLegalCaseStatus(selected.id, status);
                  if (!result.ok) {
                    toast({ title: "Durum güncellenemedi", description: result.error.message, tone: "error" });
                    return;
                  }
                  setSelected(result.data);
                  void load();
                }}
              >
                → {LEGAL_STATUS_LABELS[status] || status}
              </Button>
            ))}
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold">Aktiviteler</h3>
              <ul className="mt-2 space-y-2 text-sm">
                {(selected.activities || []).slice(0, 8).map((a) => (
                  <li key={a.id} className="rounded-lg bg-slate-50 p-2">
                    <p className="font-medium">{a.summary}</p>
                    <p className="text-xs text-slate-500">{a.notes}</p>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold">Durum geçmişi</h3>
              <ul className="mt-2 space-y-2 text-sm">
                {(selected.status_history || []).slice(0, 8).map((h) => (
                  <li key={h.id} className="rounded-lg bg-slate-50 p-2">
                    {(LEGAL_STATUS_LABELS[h.from_status] || h.from_status || "—") +
                      " → " +
                      (LEGAL_STATUS_LABELS[h.to_status] || h.to_status)}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {!lawyerPortal && selected.customer ? (
            <p className="mt-4 text-xs">
              <Link href={`/customers/${selected.customer}`} className="text-brand underline">
                Müşteri kaydına git
              </Link>
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
