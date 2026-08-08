"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Button, ButtonLink } from "./button";

export type EmptyStateProps = {
  /** Ne eksik? */
  title: string;
  /** Kullanıcı ne yapmalı? (kısa açıklama) */
  description?: string;
  /** Neden önemli? */
  why?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionHref?: string;
  secondaryLabel?: string;
  onSecondaryAction?: () => void;
  secondaryHref?: string;
  icon?: ReactNode;
  className?: string;
};

/** NP-470 — what / why / action empty state. */
export function EmptyState({
  title,
  description,
  why,
  actionLabel,
  onAction,
  actionHref,
  secondaryLabel,
  onSecondaryAction,
  secondaryHref,
  icon,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-[var(--radius-lg)] border border-dashed border-border-strong bg-surface-primary px-6 py-12 text-center",
        className,
      )}
    >
      {icon ? (
        <div className="mb-3 text-muted" aria-hidden>
          {icon}
        </div>
      ) : null}
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {description ? <p className="mt-2 max-w-md text-sm text-muted">{description}</p> : null}
      {why ? <p className="mt-1 max-w-md text-xs text-subtle">{why}</p> : null}
      {actionLabel && (onAction || actionHref) ? (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {actionHref ? (
            <ButtonLink href={actionHref}>{actionLabel}</ButtonLink>
          ) : (
            <Button onClick={onAction}>{actionLabel}</Button>
          )}
          {secondaryLabel && (onSecondaryAction || secondaryHref) ? (
            secondaryHref ? (
              <ButtonLink href={secondaryHref} variant="outline">
                {secondaryLabel}
              </ButtonLink>
            ) : (
              <Button variant="outline" onClick={onSecondaryAction}>
                {secondaryLabel}
              </Button>
            )
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
