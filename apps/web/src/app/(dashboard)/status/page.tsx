"use client";

import { useEffect, useState } from "react";

import { env } from "@/lib/env";

type StatusPayload = {
  overall: string;
  components: Array<{ code: string; name: string; state: string; message: string }>;
};

export default function StatusPage() {
  const [data, setData] = useState<StatusPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const base = env.apiUrl.replace(/\/$/, "");
    void fetch(`${base}/api/ops/status/`)
      .then(async (r) => {
        if (!r.ok) throw new Error("Status alınamadı");
        return r.json();
      })
      .then((json) => setData(json as StatusPayload))
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <p className="text-sm font-medium text-teal-800">NakitPilot</p>
        <h1 className="mt-1 font-serif text-3xl tracking-tight text-slate-900">Sistem durumu</h1>
        <p className="mt-2 text-sm text-slate-600">NP-335 — servis bileşenlerinin anlık sağlığı.</p>
      </header>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {data ? (
        <>
          <p className="text-sm">
            Genel: <span className="font-semibold">{data.overall}</span>
          </p>
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {data.components.map((c) => (
              <li key={c.code} className="flex items-center justify-between px-4 py-3 text-sm">
                <span>{c.name}</span>
                <span className="tabular-nums text-slate-700">{c.state}</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        !error && <p className="text-sm text-slate-500">Yükleniyor…</p>
      )}
    </div>
  );
}
