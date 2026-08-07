import { ERROR_MESSAGES, ERROR_TITLES, kindFromStatus } from "./messages";
import type { AppError, AppErrorKind } from "./types";

/**
 * HTTP status + JSON body → standart AppError.
 * DRF alan hataları (`{ field: ["msg"] }`) ve `detail` / `code` desteklenir.
 */
export function mapApiError(status: number, body: unknown = null): AppError {
  const kind = kindFromStatus(status);
  const code = extractCode(body);
  const fieldErrors = extractFieldErrors(body);
  const detailMessage = extractDetailMessage(body);

  return {
    kind,
    status,
    title: ERROR_TITLES[kind],
    message: detailMessage ?? ERROR_MESSAGES[kind],
    fieldErrors: Object.keys(fieldErrors).length > 0 ? fieldErrors : undefined,
    code: code ?? undefined,
    raw: body,
  };
}

export function networkError(cause?: unknown): AppError {
  return {
    kind: "network",
    status: null,
    title: ERROR_TITLES.network,
    message: ERROR_MESSAGES.network,
    raw: cause,
  };
}

export function appError(
  kind: AppErrorKind,
  overrides?: Partial<Pick<AppError, "message" | "code" | "fieldErrors" | "raw" | "status">>,
): AppError {
  return {
    kind,
    status: overrides?.status ?? null,
    title: ERROR_TITLES[kind],
    message: overrides?.message ?? ERROR_MESSAGES[kind],
    fieldErrors: overrides?.fieldErrors,
    code: overrides?.code,
    raw: overrides?.raw,
  };
}

function extractCode(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const record = body as Record<string, unknown>;
  if (typeof record.code === "string") return record.code;
  const detail = record.detail;
  if (detail && typeof detail === "object" && detail !== null) {
    const detailRecord = detail as Record<string, unknown>;
    if (typeof detailRecord.code === "string") return detailRecord.code;
  }
  return null;
}

function extractDetailMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const record = body as Record<string, unknown>;

  if (typeof record.detail === "string") return record.detail;
  if (typeof record.message === "string") return record.message;
  if (typeof record.error === "string") return record.error;

  if (Array.isArray(record.non_field_errors) && record.non_field_errors.length > 0) {
    return String(record.non_field_errors[0]);
  }

  const detail = record.detail;
  if (detail && typeof detail === "object" && detail !== null && !Array.isArray(detail)) {
    const detailRecord = detail as Record<string, unknown>;
    if (typeof detailRecord.message === "string") return detailRecord.message;
    if (typeof detailRecord.detail === "string") return detailRecord.detail;
  }

  return null;
}

/**
 * DRF-style field errors → flat map.
 * Supports top-level `{ email: ["…"] }`, `{ errors: { … } }`, nested one level.
 */
export function extractFieldErrors(body: unknown): Record<string, string> {
  if (!body || typeof body !== "object") return {};
  const record = body as Record<string, unknown>;

  const source =
    record.errors && typeof record.errors === "object" && !Array.isArray(record.errors)
      ? (record.errors as Record<string, unknown>)
      : record;

  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(source)) {
    if (RESERVED_KEYS.has(key)) continue;
    const message = firstErrorMessage(value);
    if (message) result[key] = message;
  }
  return result;
}

const RESERVED_KEYS = new Set([
  "detail",
  "code",
  "message",
  "error",
  "errors",
  "non_field_errors",
  "status",
  "status_code",
]);

function firstErrorMessage(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (Array.isArray(value) && value.length > 0) {
    const first = value[0];
    if (typeof first === "string") return first;
    if (first && typeof first === "object" && "message" in first) {
      const msg = (first as { message?: unknown }).message;
      if (typeof msg === "string") return msg;
    }
  }
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const nested = value as Record<string, unknown>;
    if (typeof nested.message === "string") return nested.message;
    // Take first nested field message (one level)
    for (const nestedValue of Object.values(nested)) {
      const msg = firstErrorMessage(nestedValue);
      if (msg) return msg;
    }
  }
  return null;
}
