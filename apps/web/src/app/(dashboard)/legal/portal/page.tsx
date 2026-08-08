import type { Metadata } from "next";

import { LegalCasesBoard } from "@/components/legal/legal-cases-board";

export const metadata: Metadata = {
  title: "Avukat portalı",
};

export default function LawyerPortalPage() {
  return <LegalCasesBoard lawyerPortal />;
}
