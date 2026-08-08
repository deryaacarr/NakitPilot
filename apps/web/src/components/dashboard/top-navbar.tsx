"use client";

import { ThemeToggle } from "@/components/ui/theme-toggle";

import { Breadcrumb } from "./breadcrumb";
import { useDashboard } from "./dashboard-context";
import { GlobalSearch } from "./global-search";
import { NotificationArea } from "./notification-area";
import { QuickCreateMenu } from "./quick-create-menu";
import { UserMenu } from "./user-menu";

export function TopNavbar() {
  const { organization, openSidebar } = useDashboard();

  return (
    <header className="sticky top-0 z-20 border-b border-border-default bg-surface-primary/90 backdrop-blur">
      <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
        <button
          type="button"
          className="rounded-[var(--radius-md)] p-2 text-muted hover:bg-surface-tertiary hover:text-foreground lg:hidden"
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

        <div className="hidden min-w-0 w-40 shrink-0 lg:block">
          <p className="truncate text-sm font-semibold text-foreground">{organization.name}</p>
          <div className="mt-0.5">
            <Breadcrumb />
          </div>
        </div>

        <GlobalSearch />

        <div className="flex shrink-0 items-center gap-1 sm:gap-2">
          <QuickCreateMenu />
          <ThemeToggle />
          <NotificationArea />
          <UserMenu />
        </div>
      </div>
      <div className="border-t border-border-default px-4 py-2 lg:hidden">
        <p className="truncate text-xs font-semibold text-foreground">{organization.name}</p>
        <div className="mt-1">
          <Breadcrumb />
        </div>
      </div>
    </header>
  );
}
