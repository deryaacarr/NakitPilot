import type { Metadata } from "next";

import { CustomerListView } from "@/components/customers/customer-list-view";

export const metadata: Metadata = {
  title: "Müşteriler",
};

export default function CustomersPage() {
  return <CustomerListView />;
}
