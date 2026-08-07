import type { Metadata } from "next";

import { KolayBiConnectionPanel } from "@/components/integrations/kolaybi-connection-panel";
import { GuidancePanel } from "@/components/onboarding/guidance-panel";
import { AIUsagePanel } from "@/components/settings/ai-usage-panel";
import { EmailProviderPanel } from "@/components/settings/email-provider-panel";
import { GovernancePanel } from "@/components/settings/governance-panel";
import { SubscriptionPanel } from "@/components/settings/subscription-panel";

export const metadata: Metadata = {
  title: "Ayarlar",
};

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">Ayarlar</h1>
        <p className="mt-1 text-sm text-slate-600">
          Abonelik, kurumsal yetki/KVKK, entegrasyonlar, e-posta/SMTP ve AI maliyet kontrolü.
        </p>
      </div>
      <SubscriptionPanel />
      <GovernancePanel />
      <GuidancePanel />
      <EmailProviderPanel />
      <AIUsagePanel />
      <KolayBiConnectionPanel />
    </div>
  );
}
