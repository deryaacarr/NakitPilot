import Link from "next/link";

import { env } from "@/lib/env";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <p className="font-serif text-3xl tracking-tight text-slate-900 sm:text-4xl">
          {env.appName}
        </p>
        <p className="max-w-xl text-base leading-7 text-slate-600">
          Gecikmiş faturalar, bugün aranacak müşteriler ve tahsilat beklentisi tek yerde.
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Link
          href="/login"
          className="bg-brand text-brand-foreground inline-flex rounded-lg px-4 py-2.5 text-sm font-semibold transition hover:bg-teal-800"
        >
          Giriş yap
        </Link>
        <Link
          href="/dashboard"
          className="inline-flex rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-800 transition hover:bg-slate-50"
        >
          Dashboard
        </Link>
      </div>
    </div>
  );
}
