"use client";

import { ImpersonationBanner } from "@/components/platform/impersonation-banner";

import { DashboardProvider } from "./dashboard-context";
import { MobileSidebar, Sidebar } from "./sidebar";
import { TopNavbar } from "./top-navbar";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <DashboardProvider>
      <div className="flex min-h-full flex-1 bg-background">
        <Sidebar />
        <MobileSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <ImpersonationBanner />
          <TopNavbar />
          <main className="flex-1 px-[var(--space-4)] py-[var(--space-6)] sm:px-[var(--space-6)] lg:px-[var(--space-8)]">
            {children}
          </main>
        </div>
      </div>
    </DashboardProvider>
  );
}
