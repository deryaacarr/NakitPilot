"use client";

import { DashboardProvider } from "./dashboard-context";
import { MobileSidebar, Sidebar } from "./sidebar";
import { TopNavbar } from "./top-navbar";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <DashboardProvider>
      <div className="flex min-h-full flex-1 bg-slate-50">
        <Sidebar />
        <MobileSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopNavbar />
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>
    </DashboardProvider>
  );
}
