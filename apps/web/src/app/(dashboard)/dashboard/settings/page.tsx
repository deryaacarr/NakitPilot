import type { Metadata } from "next";

import { KolayBiConnectionPanel } from "@/components/integrations/kolaybi-connection-panel";
import { AIUsagePanel } from "@/components/settings/ai-usage-panel";
import { EmailProviderPanel } from "@/components/settings/email-provider-panel";

export const metadata: Metadata = {
  title: "Ayarlar",
};

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Ayarlar</h1>
        <p className="mt-1 text-sm text-slate-600">
          Organizasyon entegrasyonları, e-posta/SMTP, AI maliyet kontrolü ve hesap bağlantıları.
        </p>
      </div>
      <EmailProviderPanel />
      <AIUsagePanel />
      <KolayBiConnectionPanel />
    </div>
  );
}
