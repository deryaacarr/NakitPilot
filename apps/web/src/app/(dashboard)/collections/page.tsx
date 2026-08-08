import type { Metadata } from "next";
import Link from "next/link";

import { CollectionsBoard } from "@/components/collections/collections-board";

export const metadata: Metadata = {
  title: "Tahsilat",
};

export default function CollectionsPage() {
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Link
          href="/collections/field"
          className="text-sm font-semibold text-brand underline-offset-2 hover:underline"
        >
          Saha / PWA ekranı →
        </Link>
      </div>
      <CollectionsBoard />
    </div>
  );
}
