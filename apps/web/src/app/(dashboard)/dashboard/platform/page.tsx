import type { Metadata } from "next";

import { PlatformConsole } from "@/components/platform/platform-console";

export const metadata: Metadata = {
  title: "Platform yönetimi",
};

export default function PlatformAdminPage() {
  return <PlatformConsole />;
}
