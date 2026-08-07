/**
 * Frontend genel hata türleri (NP-034).
 */

export type AppErrorKind =
  "unauthorized" | "forbidden" | "not_found" | "validation" | "server" | "network";

export type AppError = {
  kind: AppErrorKind;
  /** HTTP status; network için null */
  status: number | null;
  title: string;
  message: string;
  /** Alan → ilk hata mesajı (400/422) */
  fieldErrors?: Record<string, string>;
  /** Backend `code` alanı varsa */
  code?: string;
  raw?: unknown;
};

export function isAppError(value: unknown): value is AppError {
  return (
    typeof value === "object" &&
    value !== null &&
    "kind" in value &&
    "title" in value &&
    "message" in value
  );
}
