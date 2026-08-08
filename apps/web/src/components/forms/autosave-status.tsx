"use client";

import { cn } from "@/lib/cn";
import type { AutosaveStatus } from "@/lib/forms/use-autosave";

export function AutosaveIndicator({
  status,
  errorMessage,
  className,
}: {
  status: AutosaveStatus;
  errorMessage?: string | null;
  className?: string;
}) {
  if (status === "idle") return null;
  return (
    <p
      className={cn(
        "text-xs",
        status === "error" ? "text-danger-foreground" : "text-muted",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      {status === "saving" ? "Kaydediliyor…" : null}
      {status === "saved" ? "Kaydedildi" : null}
      {status === "error" ? errorMessage || "Kayıt başarısız — veriniz kaybolmadı" : null}
    </p>
  );
}
