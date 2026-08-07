import type { AppError } from "./types";

export type HandleAppErrorOptions = {
  /** Toast göster (useToast.toast) */
  toast?: (input: { title: string; description?: string; tone?: "error" | "warning" }) => void;
  /** 401 sonrası yönlendirme; varsayılan /login */
  onUnauthorized?: () => void;
  /** validation alan hataları ayrı işlenecekse toast atlama */
  skipToastForValidation?: boolean;
};

/**
 * Ortak UI tepkisi: toast + 401 yönlendirme.
 * Form alan hataları için `applyBackendFieldErrors` ile birlikte kullanın.
 */
export function handleAppError(error: AppError, options: HandleAppErrorOptions = {}): void {
  const { toast, onUnauthorized, skipToastForValidation = false } = options;

  if (error.kind === "unauthorized") {
    toast?.({ title: error.title, description: error.message, tone: "error" });
    onUnauthorized?.();
    return;
  }

  if (error.kind === "validation" && skipToastForValidation && error.fieldErrors) {
    return;
  }

  toast?.({
    title: error.title,
    description: error.message,
    tone: error.kind === "forbidden" ? "warning" : "error",
  });
}

export function loginRedirectPath(nextPath?: string): string {
  const next = nextPath && nextPath.startsWith("/") && !nextPath.startsWith("//") ? nextPath : "";
  return next ? `/login?next=${encodeURIComponent(next)}` : "/login";
}
