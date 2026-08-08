"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";

import { env } from "@/lib/env";

import { useDashboard } from "./dashboard-context";
import { isNavActive, NAV_GROUPS, NAV_SECONDARY, type NavLeaf } from "./nav-config";
import { NavIcon } from "./nav-icon";

function NavLink({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavLeaf;
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const active = isNavActive(pathname, item);

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      title={collapsed ? item.label : undefined}
      className={[
        "flex items-center gap-3 rounded-[var(--radius-md)] px-3 py-2 text-sm font-medium transition",
        collapsed ? "justify-center px-2" : "",
        active
          ? "bg-primary/10 text-primary ring-1 ring-primary/20"
          : "text-muted hover:bg-surface-tertiary hover:text-foreground",
      ].join(" ")}
      aria-current={active ? "page" : undefined}
    >
      <NavIcon name={item.icon} />
      {!collapsed ? <span className="truncate">{item.label}</span> : null}
    </Link>
  );
}

function NavLinks({
  collapsed,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const [secondaryOpen, setSecondaryOpen] = useState(false);

  const openGroups = useMemo(() => {
    const open = new Set<string>();
    for (const group of NAV_GROUPS) {
      if (group.items.some((item) => isNavActive(pathname, item))) {
        open.add(group.id);
      }
    }
    return open;
  }, [pathname]);

  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  function isGroupOpen(id: string) {
    if (id in expanded) return expanded[id];
    return openGroups.has(id) || id === "home";
  }

  return (
    <nav className="flex flex-1 flex-col gap-3 overflow-y-auto px-2 py-3" aria-label="Ana menü">
      {NAV_GROUPS.map((group) => {
        const open = collapsed ? true : isGroupOpen(group.id);
        const isSingleHome = group.id === "home";

        return (
          <div key={group.id}>
            {!collapsed && !isSingleHome ? (
              <button
                type="button"
                className="mb-1 flex w-full items-center justify-between px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-subtle"
                onClick={() =>
                  setExpanded((prev) => ({ ...prev, [group.id]: !isGroupOpen(group.id) }))
                }
                aria-expanded={open}
              >
                <span>{group.label}</span>
                <span aria-hidden>{open ? "−" : "+"}</span>
              </button>
            ) : null}
            {(open || isSingleHome) && (
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={`${group.id}-${item.href}-${item.label}`}
                    item={item}
                    collapsed={collapsed}
                    onNavigate={onNavigate}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}

      <div className="mt-auto border-t border-border-default pt-3">
        {!collapsed ? (
          <button
            type="button"
            className="mb-1 flex w-full items-center justify-between px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-subtle"
            onClick={() => setSecondaryOpen((v) => !v)}
            aria-expanded={secondaryOpen}
          >
            <span>Diğer</span>
            <span aria-hidden>{secondaryOpen ? "−" : "+"}</span>
          </button>
        ) : null}
        {(collapsed || secondaryOpen) && (
          <div className="flex flex-col gap-0.5">
            {NAV_SECONDARY.map((item) => (
              <NavLink
                key={item.href}
                item={item}
                collapsed={collapsed}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebarCollapsed } = useDashboard();

  return (
    <aside
      className={[
        "hidden h-full shrink-0 flex-col border-r border-border-default bg-surface-primary transition-[width] duration-200 lg:flex",
        sidebarCollapsed ? "w-[4.5rem]" : "w-64",
      ].join(" ")}
    >
      <div className="flex h-14 items-center justify-between gap-2 border-b border-border-default px-3">
        {!sidebarCollapsed ? (
          <Link href="/dashboard" className="font-serif text-xl tracking-tight text-foreground">
            {env.appName}
          </Link>
        ) : (
          <Link
            href="/dashboard"
            className="mx-auto font-serif text-lg font-semibold text-primary"
            title={env.appName}
          >
            N
          </Link>
        )}
        <button
          type="button"
          onClick={toggleSidebarCollapsed}
          className="rounded-[var(--radius-md)] p-2 text-muted hover:bg-surface-tertiary hover:text-foreground"
          aria-label={sidebarCollapsed ? "Kenar çubuğunu genişlet" : "Kenar çubuğunu daralt"}
          title={sidebarCollapsed ? "Genişlet" : "Daralt"}
        >
          <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2">
            {sidebarCollapsed ? (
              <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
            ) : (
              <path d="M15 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
            )}
          </svg>
        </button>
      </div>
      <NavLinks collapsed={sidebarCollapsed} />
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
          "absolute inset-0 bg-surface-inverse/40 transition-opacity",
          sidebarOpen ? "opacity-100" : "opacity-0",
        ].join(" ")}
        onClick={closeSidebar}
      />
      <aside
        className={[
          "absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col bg-surface-primary shadow-[var(--shadow-lg)] transition-transform duration-200",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
        aria-hidden={!sidebarOpen}
        role="dialog"
        aria-modal="true"
        aria-label="Navigasyon"
      >
        <div className="flex h-14 items-center justify-between border-b border-border-default px-4">
          <Link
            href="/dashboard"
            onClick={closeSidebar}
            className="font-serif text-xl tracking-tight text-foreground"
          >
            {env.appName}
          </Link>
          <button
            type="button"
            onClick={closeSidebar}
            className="rounded-[var(--radius-md)] p-2 text-muted hover:bg-surface-tertiary hover:text-foreground"
            aria-label="Kapat"
          >
            <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <NavLinks onNavigate={closeSidebar} />
      </aside>
    </div>
  );
}
