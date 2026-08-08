"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { enableSampleData } from "@/lib/onboarding/api";

export function DashboardEmptyState({ onSampleLoaded }: { onSampleLoaded?: () => void }) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);

  async function trySample() {
    setLoading(true);
    const res = await enableSampleData();
    setLoading(false);
    if (!res.ok) {
      toast({ title: "Örnek veri yüklenemedi", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Örnek veri hazır", tone: "success" });
    onSampleLoaded?.();
  }

  return (
    <section className="rounded-[var(--radius-lg)] border border-dashed border-border-strong bg-surface-secondary px-6 py-12 text-center">
      <h2 className="font-serif text-2xl tracking-tight text-foreground">
        Henüz müşteri veriniz bulunmuyor
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted">
        KolayBi hesabınızı bağlayın veya Excel ile veri yükleyin. İlk kayıtlarla bugünkü aksiyon
        listeniz dolmaya başlar.
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        <Link
          href="/dashboard/settings#integrations"
          className="inline-flex h-[var(--control-height-md)] items-center rounded-[var(--radius-md)] bg-primary px-4 text-sm font-semibold text-primary-foreground"
        >
          KolayBi bağla
        </Link>
        <Link
          href="/imports"
          className="inline-flex h-[var(--control-height-md)] items-center rounded-[var(--radius-md)] border border-border-default bg-surface-primary px-4 text-sm font-semibold text-foreground"
        >
          Excel yükle
        </Link>
        <Button type="button" variant="secondary" loading={loading} disabled={loading} onClick={() => void trySample()}>
          Örnek veri ile dene
        </Button>
      </div>
    </section>
  );
}
