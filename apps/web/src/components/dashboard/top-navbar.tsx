"use client";

import { useDashboard } from "./dashboard-context";
import { Breadcrumb } from "./breadcrumb";
import { NotificationArea } from "./notification-area";
import { UserMenu } from "./user-menu";

export function TopNavbar() {
  const { organization, openSidebar } = useDashboard();

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
        <button
          type="button"
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900 lg:hidden"
          aria-label="Menüyü aç"
          onClick={openSidebar}
        >
          <svg
            viewBox="0 0 24 24"
            className="size-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
          </svg>
        </button>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900">{organization.name}</p>
          <div className="mt-0.5 hidden sm:block">
            <Breadcrumb />
          </div>
        </div>

        <div className="flex items-center gap-1 sm:gap-2">
          <NotificationArea />
          <UserMenu />
        </div>
      </div>
      <div className="border-t border-slate-100 px-4 py-2 sm:hidden">
        <Breadcrumb />
      </div>
    </header>
  );
}
