"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  disableSampleData,
  enableSampleData,
  fetchOnboarding,
  trackProductEvent,
  updateOnboarding,
  type OnboardingState,
} from "@/lib/onboarding/api";

const STEP_HINTS: Record<string, string> = {
  company: "Şirket unvanı, vergi no ve iletişim bilgilerinizi tamamlayın.",
  invite: "Ekip arkadaşlarınızı davet ederek tahsilatı birlikte yönetin.",
  data_source: "KolayBi veya dosya içe aktarma ile veri kaynağını seçin.",
  first_import: "İlk müşteri ve fatura aktarımını başlatın.",
  risk: "Risk eşiklerini ve izleme tercihlerini ayarlayın.",
  workflow: "İlk tahsilat workflow’unu oluşturup yayınlayın.",
  dashboard: "Özet panoda sonuçları görün; sihirbazı tamamlayın.",
};

export function OnboardingWizard() {
  const [state, setState] = useState<OnboardingState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const result = await fetchOnboarding();
    if (!result.ok) {
      setError(result.error.message);
      return;
    }
    setState(result.data);
    setError(null);
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const stepIndex = useMemo(() => {
    if (!state) return 0;
    return Math.max(
      0,
      state.steps.findIndex((s) => s.key === state.current_step),
    );
  }, [state]);

  async function goTo(index: number, complete = false) {
    if (!state) return;
    setBusy(true);
    const target = state.steps[Math.min(Math.max(index, 0), state.steps.length - 1)];
    const completed = [...new Set([...state.completed_steps, ...state.steps.slice(0, index).map((s) => s.key)])];
    const result = await updateOnboarding({
      current_step: target.key,
      completed_steps: completed,
      wizard_completed: complete || target.key === "dashboard" ? complete : undefined,
    });
    if (!result.ok) setError(result.error.message);
    else {
      setState({ ...state, ...result.data, steps: state.steps, progress: result.data.progress ?? state.progress });
      void trackProductEvent("onboarding_step_completed", { step: target.key });
    }
    setBusy(false);
  }

  async function toggleSample(enable: boolean) {
    setBusy(true);
    const result = enable ? await enableSampleData() : await disableSampleData();
    if (!result.ok) setError(result.error.message);
    else await reload();
    setBusy(false);
  }

  if (!state && !error) {
    return <p className="text-sm text-slate-500">Onboarding yükleniyor…</p>;
  }

  if (!state) {
    return <p className="text-sm text-rose-600">{error}</p>;
  }

  const current = state.steps[stepIndex];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <p className="text-sm font-medium text-teal-800">NakitPilot</p>
        <h1 className="mt-1 font-serif text-3xl tracking-tight text-slate-900">Kurulum sihirbazı</h1>
        <p className="mt-2 text-sm text-slate-600">
          Adım {stepIndex + 1} / {state.steps.length} · Benimseme puanı %{state.progress.score}
        </p>
      </header>

      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <ol className="grid gap-2 sm:grid-cols-7">
        {state.steps.map((s, i) => {
          const done = state.completed_steps.includes(s.key) || i < stepIndex;
          const active = i === stepIndex;
          return (
            <li
              key={s.key}
              className={`rounded-lg px-2 py-2 text-center text-[11px] leading-tight ${
                active
                  ? "bg-teal-800 text-white"
                  : done
                    ? "bg-teal-50 text-teal-900"
                    : "bg-slate-100 text-slate-500"
              }`}
            >
              {s.label}
            </li>
          );
        })}
      </ol>

      <section className="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-teal-50/40 p-6">
        <h2 className="text-lg font-semibold text-slate-900">{current?.label}</h2>
        <p className="mt-2 text-sm text-slate-600">{STEP_HINTS[current?.key ?? ""]}</p>

        {current?.key === "data_source" || current?.key === "first_import" ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void toggleSample(true)}
              className="rounded-lg bg-teal-800 px-3 py-2 text-sm text-white"
            >
              Örnek veriyi yükle (20 müşteri / 50 fatura)
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void toggleSample(false)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              Örnek veriyi kaldır
            </button>
            <Link href="/imports" className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
              Gerçek veri aktar
            </Link>
          </div>
        ) : null}

        {current?.key === "invite" ? (
          <Link
            href="/dashboard/settings"
            className="mt-4 inline-block rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            Kullanıcı davetlerine git
          </Link>
        ) : null}

        {current?.key === "workflow" ? (
          <Link
            href="/dashboard/workflows"
            className="mt-4 inline-block rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            İş akışlarını aç
          </Link>
        ) : null}

        {current?.key === "dashboard" ? (
          <Link
            href="/dashboard"
            className="mt-4 inline-block rounded-lg bg-slate-900 px-3 py-2 text-sm text-white"
          >
            Dashboard’a git
          </Link>
        ) : null}

        <div className="mt-6 flex justify-between">
          <button
            type="button"
            disabled={busy || stepIndex === 0}
            onClick={() => void goTo(stepIndex - 1)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-40"
          >
            Geri
          </button>
          {stepIndex < state.steps.length - 1 ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void goTo(stepIndex + 1)}
              className="rounded-lg bg-teal-800 px-3 py-2 text-sm text-white"
            >
              İleri
            </button>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => void goTo(stepIndex, true)}
              className="rounded-lg bg-teal-800 px-3 py-2 text-sm text-white"
            >
              Sihirbazı tamamla
            </button>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-900">İlerleme puanı</h3>
        <ul className="mt-3 space-y-2 text-sm">
          {state.progress.items.map((item) => (
            <li key={item.key} className="flex justify-between gap-2">
              <span>
                {item.done ? "✓" : "○"} {item.label}
              </span>
              <span className="text-slate-500">%{item.weight}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
