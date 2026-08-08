"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

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
  sidebarCollapsed: boolean;
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
  toggleSidebarCollapsed: () => void;
  setSidebarCollapsed: (value: boolean) => void;
};

const DashboardContext = createContext<DashboardContextValue | null>(null);
const COLLAPSE_KEY = "nakitpilot.sidebar_collapsed";

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
  const [sidebarCollapsed, setSidebarCollapsedState] = useState(false);
  const [organization] = useState(DEFAULT_ORG);
  const [user] = useState(DEFAULT_USER);
  const [notifications] = useState(DEFAULT_NOTIFICATIONS);

  useEffect(() => {
    const stored = window.localStorage.getItem(COLLAPSE_KEY);
    if (stored === "1") setSidebarCollapsedState(true);
  }, []);

  const openSidebar = useCallback(() => setSidebarOpen(true), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);
  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), []);
  const setSidebarCollapsed = useCallback((value: boolean) => {
    setSidebarCollapsedState(value);
    window.localStorage.setItem(COLLAPSE_KEY, value ? "1" : "0");
  }, []);
  const toggleSidebarCollapsed = useCallback(() => {
    setSidebarCollapsedState((prev) => {
      const next = !prev;
      window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }, []);

  const value = useMemo<DashboardContextValue>(
    () => ({
      organization,
      user,
      notifications,
      unreadCount: notifications.filter((n) => !n.read).length,
      sidebarOpen,
      sidebarCollapsed,
      openSidebar,
      closeSidebar,
      toggleSidebar,
      toggleSidebarCollapsed,
      setSidebarCollapsed,
    }),
    [
      organization,
      user,
      notifications,
      sidebarOpen,
      sidebarCollapsed,
      openSidebar,
      closeSidebar,
      toggleSidebar,
      toggleSidebarCollapsed,
      setSidebarCollapsed,
    ],
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
