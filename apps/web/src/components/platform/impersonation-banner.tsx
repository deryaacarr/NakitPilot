"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { saveTokens } from "@/lib/auth/storage";
import { endImpersonation, fetchImpersonationStatus } from "@/lib/platform/api";
import type { ImpersonationStatus } from "@/lib/platform/types";

const STAFF_TOKEN_BACKUP = "nakitpilot.staff_token_backup";

export function ImpersonationBanner() {
  const [status, setStatus] = useState<ImpersonationStatus | null>(null);

  useEffect(() => {
    void fetchImpersonationStatus().then((result) => {
      if (result.ok) setStatus(result.data);
    });
  }, []);

  if (!status?.active) return null;

  return (
    <div className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-950">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p>
          {status.banner ||
            `Destek modu aktif (${status.staff_email} → ${status.target_email}). Hassas işlemler engelli.`}
        </p>
        <Button
          size="sm"
          variant="secondary"
          onClick={async () => {
            await endImpersonation(status.session_id);
            const backup = sessionStorage.getItem(STAFF_TOKEN_BACKUP);
            if (backup) {
              const tokens = JSON.parse(backup) as {
                access: string;
                refresh: string;
                remember?: boolean;
              };
              saveTokens(tokens.access, tokens.refresh, Boolean(tokens.remember));
              sessionStorage.removeItem(STAFF_TOKEN_BACKUP);
            }
            window.location.href = "/dashboard/platform";
          }}
        >
          Destek oturumunu bitir
        </Button>
      </div>
    </div>
  );
}
