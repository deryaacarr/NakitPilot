import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { AppError } from "@/lib/errors";

export type ErrorStateProps = {
  error: AppError | string;
  onRetry?: () => void;
  /** NP-472 — secondary CTA */
  secondaryLabel?: string;
  onSecondaryAction?: () => void;
  secondaryHref?: string;
  /** e.g. "Son başarılı eşitleme: 48 dakika önce" */
  meta?: string;
  className?: string;
  children?: ReactNode;
};

/** NP-472 — friendly error with retry + secondary action. */
export function ErrorState({
  error,
  onRetry,
  secondaryLabel,
  onSecondaryAction,
  secondaryHref,
  meta,
  className,
  children,
}: ErrorStateProps) {
  const title = typeof error === "string" ? "Bir sorun oluştu" : error.title;
  const message = typeof error === "string" ? error : error.message;

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-[var(--radius-lg)] border border-danger/20 bg-danger-soft/60 px-6 py-10 text-center",
        className,
      )}
    >
      <p className="text-sm font-semibold text-danger-foreground">{title}</p>
      <p className="mt-1 max-w-md text-sm text-danger-foreground/90">{message}</p>
      {meta ? <p className="mt-2 max-w-md text-xs text-muted">{meta}</p> : null}
      {children}
      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        {onRetry ? (
          <Button variant="outline" className="min-h-11" onClick={onRetry}>
            Tekrar Dene
          </Button>
        ) : null}
        {secondaryLabel && (onSecondaryAction || secondaryHref) ? (
          secondaryHref ? (
            <Link
              href={secondaryHref}
              className="inline-flex min-h-11 items-center rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-4 text-sm font-semibold"
            >
              {secondaryLabel}
            </Link>
          ) : (
            <Button variant="secondary" className="min-h-11" onClick={onSecondaryAction}>
              {secondaryLabel}
            </Button>
          )
        ) : null}
      </div>
    </div>
  );
}

/** Common sync/integration failure (NP-472 example). */
export function SyncErrorState({
  lastSuccessLabel = "Son başarılı eşitleme bilgisi yok",
  onRetry,
}: {
  lastSuccessLabel?: string;
  onRetry?: () => void;
}) {
  return (
    <ErrorState
      error={{
        kind: "server",
        title: "KolayBi verileri şu anda eşitlenemedi.",
        message: "Mevcut verileri kullanmaya devam edebilirsiniz.",
        code: "sync_failed",
        status: 503,
      }}
      meta={lastSuccessLabel}
      onRetry={onRetry}
      secondaryLabel="Entegrasyonu Aç"
      secondaryHref="/dashboard/settings#integrations"
    />
  );
}
