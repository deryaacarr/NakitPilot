import type { Metadata } from "next";

import { PromiseCalendarBoard } from "@/components/promises/promise-calendar-board";

export const metadata: Metadata = {
  title: "Ödeme sözleri",
};

export default function PaymentPromisesPage() {
  return <PromiseCalendarBoard />;
}
