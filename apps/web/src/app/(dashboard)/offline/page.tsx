import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Çevrimdışı",
};

export default function OfflinePage() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col justify-center px-4 text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">NakitPilot</p>
      <h1 className="mt-2 font-serif text-3xl text-slate-900">Çevrimdışısınız</h1>
      <p className="mt-2 text-sm text-slate-600">
        Bağlantı gelene kadar saha kabuğu kullanılabilir. Görüşme notları ve görev tamamlamaları
        kuyruğa alınır.
      </p>
      <Link
        href="/collections/field"
        className="mt-6 inline-flex items-center justify-center rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white"
      >
        Saha ekranına dön
      </Link>
    </div>
  );
}
