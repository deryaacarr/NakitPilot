"use client";

import { ImpersonationBanner } from "@/components/platform/impersonation-banner";

import { DashboardProvider } from "./dashboard-context";
import { MobileBottomNav } from "./mobile-bottom-nav";
import { MobileSidebar, Sidebar } from "./sidebar";
import { TopNavbar } from "./top-navbar";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <DashboardProvider>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded-[var(--radius-md)] focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:text-primary-foreground"
      >
        İçeriğe atla
      </a>
      <div className="flex min-h-full flex-1 bg-background">
        <Sidebar />
        <MobileSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <ImpersonationBanner />
          <TopNavbar />
          <main
            id="main-content"
            className="flex-1 px-[var(--space-4)] py-[var(--space-6)] pb-24 sm:px-[var(--space-6)] lg:px-[var(--space-8)] lg:pb-[var(--space-6)]"
          >
            {children}
          </main>
        </div>
      </div>
      <MobileBottomNav />
    </DashboardProvider>
  );
}
