import type { ReactNode } from "react";

import { PageHeader, type PageHeaderProps } from "./page-header";
import { PageShell } from "./page-shell";

export type DetailPageProps = PageHeaderProps & {
  /** Sticky or secondary actions under header */
  meta?: ReactNode;
  /** Optional side rail (summary / health) */
  aside?: ReactNode;
  children: ReactNode;
  stickyFooter?: ReactNode;
};

/** NP-501 — Detay sayfası şablonu. */
export function DetailPage({
  meta,
  aside,
  children,
  stickyFooter,
  ...header
}: DetailPageProps) {
  return (
    <PageShell width="fluid" className="pb-20" data-template="detail">
      <PageHeader {...header} />
      {meta}
      <div className={aside ? "grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]" : undefined}>
        <div className="min-w-0 space-y-5">{children}</div>
        {aside ? <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">{aside}</aside> : null}
      </div>
      {stickyFooter ? (
        <div className="fixed inset-x-0 bottom-14 z-30 border-t border-border-default bg-surface-primary/95 px-4 py-3 backdrop-blur lg:bottom-0">
          <div className="mx-auto flex max-w-[90rem] flex-wrap gap-2">{stickyFooter}</div>
        </div>
      ) : null}
    </PageShell>
  );
}
