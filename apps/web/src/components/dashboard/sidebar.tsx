"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { env } from "@/lib/env";

import { useDashboard } from "./dashboard-context";
import { DASHBOARD_NAV } from "./nav-config";
import { NavIcon } from "./nav-icon";

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-1 flex-col gap-1 px-3 py-4" aria-label="Ana menü">
      {DASHBOARD_NAV.map((item) => {
        const active =
          item.href === "/dashboard"
            ? pathname === "/dashboard"
            : pathname === item.href || pathname.startsWith(`${item.href}/`);

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={[
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition",
              active
                ? "bg-brand/10 text-brand"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
            ].join(" ")}
            aria-current={active ? "page" : undefined}
          >
            <NavIcon name={item.icon} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden h-full w-64 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
      <div className="flex h-14 items-center border-b border-slate-200 px-5">
        <Link href="/dashboard" className="font-serif text-xl tracking-tight text-slate-900">
          {env.appName}
        </Link>
      </div>
      <NavLinks />
    </aside>
  );
}

export function MobileSidebar() {
  const { sidebarOpen, closeSidebar } = useDashboard();

  return (
    <div
      className={[
        "fixed inset-0 z-40 lg:hidden",
        sidebarOpen ? "pointer-events-auto" : "pointer-events-none",
      ].join(" ")}
    >
      <button
        type="button"
        aria-label="Menüyü kapat"
        className={[
          "absolute inset-0 bg-slate-900/40 transition-opacity",
          sidebarOpen ? "opacity-100" : "opacity-0",
        ].join(" ")}
        onClick={closeSidebar}
      />
      <aside
        className={[
          "absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col bg-white shadow-xl transition-transform duration-200",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
        aria-hidden={!sidebarOpen}
      >
        <div className="flex h-14 items-center justify-between border-b border-slate-200 px-4">
          <Link
            href="/dashboard"
            onClick={closeSidebar}
            className="font-serif text-xl tracking-tight text-slate-900"
          >
            {env.appName}
          </Link>
          <button
            type="button"
            onClick={closeSidebar}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            aria-label="Kapat"
          >
            <svg
              viewBox="0 0 24 24"
              className="size-5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <NavLinks onNavigate={closeSidebar} />
      </aside>
    </div>
  );
}
