import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { AppError } from "@/lib/errors";
import { cn } from "@/lib/cn";

export type ErrorStateProps = {
  error: AppError | string;
  onRetry?: () => void;
  className?: string;
  children?: ReactNode;
};

export function ErrorState({ error, onRetry, className, children }: ErrorStateProps) {
  const title = typeof error === "string" ? "Hata" : error.title;
  const message = typeof error === "string" ? error : error.message;

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-red-100 bg-red-50/60 px-6 py-10 text-center",
        className,
      )}
    >
      <p className="text-sm font-semibold text-red-900">{title}</p>
      <p className="mt-1 max-w-md text-sm text-red-800/80">{message}</p>
      {children}
      {onRetry ? (
        <Button variant="outline" className="mt-4" onClick={onRetry}>
          Tekrar dene
        </Button>
      ) : null}
    </div>
  );
}
