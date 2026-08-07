import type { Metadata } from "next";

import { ImportWizard } from "@/components/imports/import-wizard";

export const metadata: Metadata = {
  title: "İçe aktarma",
};

export default function ImportsPage() {
  return <ImportWizard />;
}
