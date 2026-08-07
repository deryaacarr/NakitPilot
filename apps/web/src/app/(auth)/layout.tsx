import Link from "next/link";

import { env } from "@/lib/env";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-full flex-1 flex-col">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(15,118,110,0.12),_transparent_55%),linear-gradient(180deg,#f8fafc_0%,#eef6f5_100%)]"
      />
      <header className="relative z-10 px-6 py-6 sm:px-10">
        <Link href="/" className="font-serif text-2xl tracking-tight text-slate-900">
          {env.appName}
        </Link>
      </header>
      <main className="relative z-10 flex flex-1 items-center justify-center px-4 pb-16">
        {children}
      </main>
    </div>
  );
}
