import type { ReactNode } from "react";

import { PageHeader, type PageHeaderProps } from "./page-header";
import { PageShell } from "./page-shell";
import { Surface } from "@/components/ui/surface";
import { cn } from "@/lib/cn";

export type SettingsNavItem = {
  id: string;
  label: string;
  href?: string;
};

export type SettingsPageProps = PageHeaderProps & {
  nav: SettingsNavItem[];
  activeId: string;
  onNavChange?: (id: string) => void;
  children: ReactNode;
};

/** NP-501 — Ayar sayfası şablonu. */
export function SettingsPage({
  nav,
  activeId,
  onNavChange,
  children,
  ...header
}: SettingsPageProps) {
  return (
    <PageShell width="reading" data-template="settings">
      <PageHeader {...header} />
      <div className="grid gap-5 md:grid-cols-[12rem_minmax(0,1fr)]">
        <nav aria-label="Ayar bölümleri" className="flex flex-row gap-1 overflow-x-auto md:flex-col">
          {nav.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavChange?.(item.id)}
              className={cn(
                "min-h-11 rounded-[var(--radius-md)] px-3 py-2 text-left text-sm font-medium whitespace-nowrap",
                activeId === item.id
                  ? "bg-primary/10 text-primary"
                  : "text-muted hover:bg-surface-secondary hover:text-foreground",
              )}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <Surface as="section" className="min-w-0">
          {children}
        </Surface>
      </div>
    </PageShell>
  );
}
