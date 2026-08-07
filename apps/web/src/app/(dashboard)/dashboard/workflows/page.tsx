import type { Metadata } from "next";

import { WorkflowListView } from "@/components/workflows/workflow-list-view";

export const metadata: Metadata = {
  title: "İş akışları",
};

export default function WorkflowsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl tracking-tight text-slate-900">İş akışları</h1>
        <p className="mt-1 text-sm text-slate-600">
          Görsel tahsilat workflow’ları — tetikleyici, koşul, bekleme ve aksiyon blokları.
        </p>
      </div>
      <WorkflowListView />
    </div>
  );
}
