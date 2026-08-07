import type { Metadata } from "next";

import { GuidancePanel } from "@/components/onboarding/guidance-panel";
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";

export const metadata: Metadata = {
  title: "Onboarding",
};

export default function OnboardingPage() {
  return (
    <div className="space-y-8">
      <OnboardingWizard />
      <GuidancePanel />
    </div>
  );
}
