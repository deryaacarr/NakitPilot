import type { Metadata } from "next";

import { DeveloperPortalView } from "@/components/developers/developer-portal-view";

export const metadata: Metadata = {
  title: "Geliştirici portalı",
};

export default function DevelopersPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Geliştirici portalı</h1>
        <p className="mt-1 text-sm text-slate-600">
          API anahtarları, dokümantasyon, webhook’lar, kullanım grafikleri ve son hatalar.
        </p>
      </div>
      <DeveloperPortalView />
    </div>
  );
}
