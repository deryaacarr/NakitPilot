"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import * as Sentry from "@sentry/nextjs";

import { getOrganizationId } from "@/lib/api/organization";
import { getAccessToken, syncAuthCookieFromStorage } from "@/lib/auth/storage";

function userIdFromAccessToken(): string | null {
  const token = getAccessToken();
  if (!token) return null;
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    const payload = JSON.parse(json) as { user_id?: number | string };
    return payload.user_id != null ? String(payload.user_id) : null;
  } catch {
    return null;
  }
}

/**
 * Client-side backup for protected routes.
 * Middleware already blocks missing cookies; this covers storage/cookie drift.
 *
 * Wait until after mount before trusting storage — SSR/hydration must not
 * treat a missing server snapshot as "logged out" and bounce to /login.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    const token = Boolean(getAccessToken());
    setHasToken(token);
    setReady(true);
    if (!token) {
      Sentry.setUser(null);
      const next = encodeURIComponent(pathname || "/dashboard");
      router.replace(`/login?next=${next}`);
      return;
    }
    syncAuthCookieFromStorage();
    const userId = userIdFromAccessToken();
    if (userId) Sentry.setUser({ id: userId });
    const orgId = getOrganizationId();
    if (orgId) Sentry.setTag("organization_id", String(orgId));
  }, [pathname, router]);

  if (!ready) {
    return (
      <div className="flex min-h-full flex-1 items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-500">Oturum kontrol ediliyor…</p>
      </div>
    );
  }

  if (!hasToken) {
    return (
      <div className="flex min-h-full flex-1 items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-500">Oturum kontrol ediliyor…</p>
      </div>
    );
  }

  return children;
}
