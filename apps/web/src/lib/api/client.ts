import {
  getAccessToken,
  getRefreshToken,
  saveTokens,
  wasRemembered,
  clearTokens,
} from "@/lib/auth/storage";
import { env } from "@/lib/env";
import {
  mapApiError,
  networkError,
  parseApiResponse,
  type ApiResult,
  type AppError,
} from "@/lib/errors";
import { getOrganizationId, setOrganizationId } from "@/lib/api/organization";

function apiBase(): string {
  return env.apiUrl.replace(/\/$/, "");
}

async function ensureOrganizationId(access: string): Promise<string | null> {
  const existing = getOrganizationId();
  if (existing) return existing;

  try {
    const response = await fetch(`${apiBase()}/api/memberships/me/`, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${access}`,
      },
    });
    if (!response.ok) return null;
    const body = (await response.json()) as Array<{ organization: number }>;
    const first = Array.isArray(body) ? body[0] : null;
    if (!first?.organization) return null;
    setOrganizationId(first.organization);
    return String(first.organization);
  } catch {
    return null;
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  try {
    const response = await fetch(`${apiBase()}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!response.ok) {
      clearTokens();
      return null;
    }
    const body = (await response.json()) as { access?: string; refresh?: string };
    if (!body.access) {
      clearTokens();
      return null;
    }
    saveTokens(body.access, body.refresh ?? refresh, wasRemembered());
    return body.access;
  } catch {
    return null;
  }
}

export type ApiRequestOptions = {
  method?: string;
  body?: unknown;
  /** multipart upload — Content-Type set by browser */
  formData?: FormData;
  query?: Record<string, string | number | boolean | undefined | null>;
  organizationId?: string | number | null;
  auth?: boolean;
};

function buildUrl(path: string, query?: ApiRequestOptions["query"]): string {
  const url = new URL(path.startsWith("http") ? path : `${apiBase()}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<ApiResult<T>> {
  const { method = "GET", body, formData, query, auth = true } = options;
  let access = auth ? getAccessToken() : null;

  if (auth && !access) {
    return {
      ok: false,
      error: mapApiError(401, { detail: "Oturum bulunamadı." }),
    };
  }

  if (auth && access) {
    await ensureOrganizationId(access);
  }

  const organizationId = options.organizationId ?? getOrganizationId();

  const doFetch = async (token: string | null) => {
    const headers: Record<string, string> = {
      Accept: "application/json",
    };
    if (formData === undefined && body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (token) headers.Authorization = `Bearer ${token}`;
    if (organizationId) headers["X-Organization-Id"] = String(organizationId);

    return fetch(buildUrl(path, query), {
      method,
      headers,
      body:
        formData !== undefined ? formData : body === undefined ? undefined : JSON.stringify(body),
    });
  };

  let response: Response;
  try {
    response = await doFetch(access);
  } catch (cause) {
    return { ok: false, error: networkError(cause) };
  }

  if (response.status === 401 && auth) {
    const next = await refreshAccessToken();
    if (!next) {
      return { ok: false, error: mapApiError(401) };
    }
    access = next;
    try {
      response = await doFetch(access);
    } catch (cause) {
      return { ok: false, error: networkError(cause) };
    }
  }

  return parseApiResponse<T>(response);
}

export type { AppError, ApiResult };
