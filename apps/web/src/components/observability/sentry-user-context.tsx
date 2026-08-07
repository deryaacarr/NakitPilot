"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

import { getOrganizationId } from "@/lib/api/organization";

/**
 * NP-183 — attach user + organization IDs (never email) after auth bootstrap.
 */
export function SentryUserContext({
  userId,
}: {
  userId?: string | number | null;
}) {
  useEffect(() => {
    if (userId != null) {
      Sentry.setUser({ id: String(userId) });
    } else {
      Sentry.setUser(null);
    }
    const orgId = getOrganizationId();
    if (orgId) {
      Sentry.setTag("organization_id", String(orgId));
    }
  }, [userId]);

  return null;
}
