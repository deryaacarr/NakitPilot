"use client";

import { useEffect, useState } from "react";

import { ErrorState } from "@/components/errors";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { fetchRiskMonitoring, type RiskMonitoringPayload } from "@/lib/risk/api";
import type { AppError } from "@/lib/errors";
import { RISK_LABELS, type RiskStatus } from "@/lib/customers/types";

function pct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return `%${Math.round(value * 1000) / 10}`;
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export function RiskMonitoringView() {
  const [data, setData] = useState<RiskMonitoringPayload | null>(null);
  const [error, setError] = useState<AppError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void fetchRiskMonitoring().then((result) => {
      if (cancelled) return;
      setLoading(false);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setData(result.data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <LoadingSkeleton lines={8} />;
  if (error) return <ErrorState error={error} />;
  if (!data) return null;

  const pvc = data.business.predicted_vs_actual_collection;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Model doğruluk</h1>
        <p className="mt-1 text-sm text-slate-600">
          Son {data.lookback_days} gün · {data.n_labeled} etiketli tahmin
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-900">Tahmin edilen / gerçekleşen tahsilat</h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Tahmin edilen tahsilat" value={String(pvc.predicted_collection)} />
          <MetricCard label="Gerçekleşen tahsilat" value={String(pvc.actual_collection)} />
          <MetricCard
            label="İkisi birden"
            value={String(pvc.predicted_and_actual_collection)}
          />
          <MetricCard label="İsabet oranı" value={pct(pvc.collection_hit_rate)} />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-900">
          Risk seviyesine göre gerçek gecikme oranı
        </h2>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold tracking-wide text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-3">Seviye</th>
                <th className="px-4 py-3">Adet</th>
                <th className="px-4 py-3">Gecikmeli</th>
                <th className="px-4 py-3">Oran</th>
              </tr>
            </thead>
            <tbody>
              {data.business.delay_rate_by_risk_level.map((row) => (
                <tr key={row.risk_level} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-3">
                    {RISK_LABELS[row.risk_level as RiskStatus] ?? row.risk_level}
                  </td>
                  <td className="px-4 py-3">{row.n}</td>
                  <td className="px-4 py-3">{row.with_delay}</td>
                  <td className="px-4 py-3">{pct(row.delay_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {data.technical_visible && data.technical ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-900">Teknik metrikler (yalnızca admin)</h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Precision" value={pct(data.technical.precision)} />
            <MetricCard label="Recall" value={pct(data.technical.recall)} />
            <MetricCard
              label="ROC-AUC"
              value={
                data.technical.roc_auc == null
                  ? "—"
                  : data.technical.roc_auc.toFixed(3)
              }
            />
            <MetricCard
              label="Calibration error"
              value={
                data.technical.calibration_error == null
                  ? "—"
                  : data.technical.calibration_error.toFixed(3)
              }
            />
          </div>
        </section>
      ) : (
        <p className="text-sm text-slate-500">
          Teknik metrikler (Precision, Recall, ROC-AUC, Calibration) yalnızca organizasyon
          yöneticilerine gösterilir.
        </p>
      )}
    </div>
  );
}
