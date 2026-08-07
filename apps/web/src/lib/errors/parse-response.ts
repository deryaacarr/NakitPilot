import { mapApiError, networkError, type AppError } from "@/lib/errors";

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: AppError };

/**
 * fetch Response → AppError veya JSON data (NP-034 yardımcı).
 */
export async function parseApiResponse<T>(response: Response): Promise<ApiResult<T>> {
  let body: unknown = null;
  const contentType = response.headers.get("content-type") ?? "";
  if (response.status !== 204 && contentType.includes("application/json")) {
    try {
      body = await response.json();
    } catch {
      body = null;
    }
  }

  if (!response.ok) {
    return { ok: false, error: mapApiError(response.status, body) };
  }

  return { ok: true, data: (body as T) ?? (null as T) };
}

export async function safeFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<{ response: Response } | { error: AppError }> {
  try {
    const response = await fetch(input, init);
    return { response };
  } catch (cause) {
    return { error: networkError(cause) };
  }
}
