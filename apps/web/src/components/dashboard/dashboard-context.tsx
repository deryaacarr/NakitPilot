"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type DashboardOrganization = {
  id: number;
  name: string;
};

export type DashboardUser = {
  email: string;
  firstName: string;
  lastName: string;
};

export type DashboardNotification = {
  id: string;
  title: string;
  read: boolean;
};

type DashboardContextValue = {
  organization: DashboardOrganization;
  user: DashboardUser;
  notifications: DashboardNotification[];
  unreadCount: number;
  sidebarOpen: boolean;
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
};

const DashboardContext = createContext<DashboardContextValue | null>(null);

const DEFAULT_ORG: DashboardOrganization = {
  id: 1,
  name: "Demo Ticaret A.Ş.",
};

const DEFAULT_USER: DashboardUser = {
  email: "finans@demo.example",
  firstName: "Ayşe",
  lastName: "Yılmaz",
};

const DEFAULT_NOTIFICATIONS: DashboardNotification[] = [
  { id: "1", title: "3 gecikmiş fatura dikkat gerektiriyor", read: false },
  { id: "2", title: "Bugün 5 müşteri aranmalı", read: false },
  { id: "3", title: "Ödeme sözü süresi doldu", read: true },
];

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [organization] = useState(DEFAULT_ORG);
  const [user] = useState(DEFAULT_USER);
  const [notifications] = useState(DEFAULT_NOTIFICATIONS);

  const openSidebar = useCallback(() => setSidebarOpen(true), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);
  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), []);

  const value = useMemo<DashboardContextValue>(
    () => ({
      organization,
      user,
      notifications,
      unreadCount: notifications.filter((n) => !n.read).length,
      sidebarOpen,
      openSidebar,
      closeSidebar,
      toggleSidebar,
    }),
    [organization, user, notifications, sidebarOpen, openSidebar, closeSidebar, toggleSidebar],
  );

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard() {
  const ctx = useContext(DashboardContext);
  if (!ctx) {
    throw new Error("useDashboard must be used within DashboardProvider");
  }
  return ctx;
}
