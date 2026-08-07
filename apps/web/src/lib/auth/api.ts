import { env } from "@/lib/env";

import { mapLoginApiError, type LoginErrorState } from "./errors";
import { saveTokens } from "./storage";

export type AuthUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  is_active: boolean;
};

export type LoginSuccess = {
  access: string;
  refresh: string;
  user: AuthUser;
};

export type LoginResult = { ok: true; data: LoginSuccess } | { ok: false; error: LoginErrorState };

function apiBase(): string {
  return env.apiUrl.replace(/\/$/, "");
}

export async function loginRequest(input: {
  email: string;
  password: string;
  remember: boolean;
}): Promise<LoginResult> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email: input.email, password: input.password }),
    });
  } catch {
    return {
      ok: false,
      error: {
        code: "network_error",
        message: "Sunucuya bağlanılamadı. Bağlantınızı kontrol edin.",
      },
    };
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    return { ok: false, error: mapLoginApiError(response.status, body) };
  }

  const data = body as LoginSuccess;
  if (!data?.access || !data?.refresh) {
    return {
      ok: false,
      error: {
        code: "server_error",
        message: "Sunucu hatası oluştu. Lütfen biraz sonra tekrar deneyin.",
      },
    };
  }

  saveTokens(data.access, data.refresh, input.remember);
  return { ok: true, data };
}
