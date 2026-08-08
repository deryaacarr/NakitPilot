import type { Metadata } from "next";

import { VisualGallery } from "@/components/design-system/visual-gallery";

export const metadata: Metadata = {
  title: "UI Gallery",
  robots: { index: false, follow: false },
};

/** NP-503 — unauthenticated visual fixtures for Playwright screenshots. */
export default function UiGalleryPage() {
  return (
    <main className="min-h-full bg-background px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-5xl space-y-2">
        <p className="np-helper uppercase tracking-[0.14em]">NP-503</p>
        <h1 className="np-page-title">UI Gallery</h1>
        <p className="np-body text-muted mb-8 max-w-prose" data-testid="prose-measure">
          Görsel regresyon fixture’ları — API ve oturum gerektirmez. Çok geniş ekranda satır
          uzunluğu bu ölçü ile sınırlanır.
        </p>
        <VisualGallery />
      </div>
    </main>
  );
}
