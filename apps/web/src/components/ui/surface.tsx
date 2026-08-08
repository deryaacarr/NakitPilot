import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export type SurfaceProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  /** muted = secondary surface (NP-500 card consolidation) */
  tone?: "default" | "muted";
  padding?: "none" | "sm" | "md" | "lg";
  as?: "div" | "section" | "article";
};

const paddingClass = {
  none: "",
  sm: "p-[var(--space-3)]",
  md: "p-[var(--space-4)]",
  lg: "p-[var(--space-6)]",
} as const;

/**
 * NP-500 — single card/panel surface. Prefer this over ad-hoc border-slate / bg-white cards.
 */
export function Surface({
  children,
  tone = "default",
  padding = "md",
  as: Tag = "div",
  className,
  ...props
}: SurfaceProps) {
  return (
    <Tag
      className={cn(
        tone === "muted" ? "np-surface-muted" : "np-surface",
        paddingClass[padding],
        className,
      )}
      {...props}
    >
      {children}
    </Tag>
  );
}
