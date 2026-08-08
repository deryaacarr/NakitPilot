import type { Metadata } from "next";

import { LegalCasesBoard } from "@/components/legal/legal-cases-board";

export const metadata: Metadata = {
  title: "Hukuki dosyalar",
};

export default function LegalPage() {
  return <LegalCasesBoard />;
}
