import type { Metadata } from "next";

import { FieldBoard } from "@/components/collections/field-board";

export const metadata: Metadata = {
  title: "Saha tahsilat",
  appleWebApp: {
    capable: true,
    title: "NakitPilot",
    statusBarStyle: "default",
  },
};

export default function FieldCollectionsPage() {
  return <FieldBoard />;
}
