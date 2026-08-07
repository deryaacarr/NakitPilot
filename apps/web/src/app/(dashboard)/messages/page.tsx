import type { Metadata } from "next";

import { MessagesView } from "@/components/messages/messages-view";

export const metadata: Metadata = {
  title: "Mesajlar",
};

export default function MessagesPage() {
  return <MessagesView />;
}
