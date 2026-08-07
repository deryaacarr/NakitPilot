import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { isAppError, type AppError } from "@/lib/errors";

/**
 * Backend alan hatalarını React Hook Form `setError` ile eşler (NP-033).
 */
export function applyBackendFieldErrors<TFieldValues extends FieldValues>(
  setError: UseFormSetError<TFieldValues>,
  error: AppError | Record<string, string>,
): void {
  const fieldErrors = isAppError(error) ? (error.fieldErrors ?? {}) : error;

  const entries = Object.entries(fieldErrors);

  if (entries.length === 0) {
    const message = isAppError(error) ? error.message : "Form hatası";
    setError("root.server" as Path<TFieldValues>, {
      type: "server",
      message,
    });
    return;
  }

  for (const [field, message] of entries) {
    setError(field as Path<TFieldValues>, {
      type: "server",
      message,
    });
  }
}
