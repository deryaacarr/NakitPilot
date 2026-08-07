"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { enableSampleData, fetchGuidance, type Guidance } from "@/lib/onboarding/api";

export function GuidancePanel() {
  const [data, setData] = useState<Guidance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchGuidance().then((result) => {
      if (!result.ok) {
        setError(result.error.message);
        return;
      }
      setData(result.data);
    });
  }, []);

  if (!data && !error) return null;
  if (!data) return <p className="text-sm text-slate-500">{error}</p>;

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Kullanım yönlendirmeleri</h2>
          <p className="mt-1 text-xs text-slate-500">
            Empty state aksiyonları, checklist, örnek rapor ve yardım.
          </p>
        </div>
        <span className="rounded bg-teal-50 px-2 py-1 text-xs font-medium text-teal-900">
          %{data.score}
        </span>
      </div>

      {data.empty_states.length > 0 ? (
        <ul className="space-y-2">
          {data.empty_states.map((e) => (
            <li key={e.surface} className="rounded-lg border border-dashed border-slate-200 p-3 text-sm">
              <p className="font-medium text-slate-900">{e.title}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Link href={e.action_href} className="text-teal-800 underline">
                  {e.action_label}
                </Link>
                {e.secondary_action === "enable_sample_data" ? (
                  <button
                    type="button"
                    className="text-slate-600 underline"
                    onClick={() => void enableSampleData()}
                  >
                    {e.secondary_label}
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Checklist</h3>
        <ul className="mt-2 space-y-1 text-sm">
          {data.checklist.map((c) => (
            <li key={c.key}>
              {c.done ? "✓" : "○"} {c.label}
            </li>
          ))}
        </ul>
      </div>

      {data.tooltips[0] ? (
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
          İpucu: {data.tooltips[0].text}
        </p>
      ) : null}

      <div className="rounded-lg border border-slate-100 p-3">
        <h3 className="text-sm font-medium text-slate-900">{data.sample_report.title}</h3>
        <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
          {data.sample_report.metrics.map((m) => (
            <div key={m.label}>
              <dt className="text-xs text-slate-500">{m.label}</dt>
              <dd className="font-medium">{m.value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-2 text-xs text-slate-500">{data.sample_report.note}</p>
      </div>

      <div className="flex flex-wrap gap-3 text-sm">
        {data.help_links.map((h) => (
          <Link key={h.href} href={h.href} className="text-teal-800 underline">
            {h.label}
          </Link>
        ))}
      </div>

      {data.announcements.length > 0 ? (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Özellik duyuruları
          </h3>
          <ul className="mt-2 space-y-2 text-sm">
            {data.announcements.map((a) => (
              <li key={a.key}>
                <span className="font-medium">{a.title}</span>
                <span className="text-slate-600"> — {a.body}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
