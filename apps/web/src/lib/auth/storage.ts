import { AUTH_COOKIE } from "@/lib/auth/constants";

const ACCESS_KEY = "nakitpilot.access";
const REFRESH_KEY = "nakitpilot.refresh";
const REMEMBER_KEY = "nakitpilot.remember";

function storage(remember: boolean): Storage {
  return remember ? window.localStorage : window.sessionStorage;
}

function clearBoth() {
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  window.sessionStorage.removeItem(ACCESS_KEY);
  window.sessionStorage.removeItem(REFRESH_KEY);
}

function setAuthCookie(access: string, remember: boolean) {
  const maxAge = remember ? 60 * 60 * 24 * 7 : undefined;
  const parts = [`${AUTH_COOKIE}=${encodeURIComponent(access)}`, "Path=/", "SameSite=Lax"];
  if (maxAge) parts.push(`Max-Age=${maxAge}`);
  document.cookie = parts.join("; ");
}

function clearAuthCookie() {
  document.cookie = `${AUTH_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}

export function saveTokens(access: string, refresh: string, remember: boolean) {
  clearBoth();
  const store = storage(remember);
  store.setItem(ACCESS_KEY, access);
  store.setItem(REFRESH_KEY, refresh);
  window.localStorage.setItem(REMEMBER_KEY, remember ? "1" : "0");
  setAuthCookie(access, remember);
}

export function clearTokens() {
  clearBoth();
  window.localStorage.removeItem(REMEMBER_KEY);
  clearAuthCookie();
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_KEY) ?? window.sessionStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return window.localStorage.getItem(REFRESH_KEY) ?? window.sessionStorage.getItem(REFRESH_KEY);
}

export function wasRemembered(): boolean {
  return window.localStorage.getItem(REMEMBER_KEY) === "1";
}

/** Keep cookie in sync when token exists only in storage (legacy sessions). */
export function syncAuthCookieFromStorage() {
  const access = getAccessToken();
  if (!access) {
    clearAuthCookie();
    return false;
  }
  setAuthCookie(access, wasRemembered());
  return true;
}
