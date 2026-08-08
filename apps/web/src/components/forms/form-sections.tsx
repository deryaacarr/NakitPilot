"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export type FormSectionDef<T extends string> = {
  id: T;
  label: string;
};

/** NP-450 — tabbed form sections. */
export function FormSectionTabs<T extends string>({
  sections,
  active,
  onChange,
  errorSections,
}: {
  sections: FormSectionDef<T>[];
  active: T;
  onChange: (id: T) => void;
  /** Highlight tabs that contain field errors */
  errorSections?: Partial<Record<T, boolean>>;
}) {
  return (
    <div className="flex flex-wrap gap-2 border-b border-border-default pb-2">
      {sections.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={cn(
            "rounded-[var(--radius-md)] px-3 py-1.5 text-sm font-medium transition",
            active === item.id
              ? "bg-primary/10 text-primary"
              : "text-muted hover:bg-surface-secondary hover:text-foreground",
            errorSections?.[item.id] && active !== item.id && "ring-1 ring-danger/40",
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function FormSectionPanel({
  title,
  description,
  children,
  className,
}: {
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4",
        className,
      )}
    >
      {title ? <h2 className="mb-1 text-sm font-semibold text-foreground">{title}</h2> : null}
      {description ? <p className="mb-3 text-xs text-muted">{description}</p> : null}
      {children}
    </section>
  );
}
