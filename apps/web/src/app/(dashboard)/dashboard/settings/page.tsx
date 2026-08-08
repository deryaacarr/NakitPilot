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
        <h1 className="np-page-title">Ayarlar</h1>
        <p className="mt-1 text-sm text-muted">
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
