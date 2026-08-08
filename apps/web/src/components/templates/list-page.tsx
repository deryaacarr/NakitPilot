import type { ReactNode } from "react";

import { PageHeader, type PageHeaderProps } from "./page-header";
import { PageShell } from "./page-shell";

export type ListPageProps = PageHeaderProps & {
  /** Filters / search toolbar */
  toolbar?: ReactNode;
  children: ReactNode;
  /** Bulk selection bar etc. */
  belowToolbar?: ReactNode;
};

/** NP-501 — Liste sayfası şablonu. */
export function ListPage({ toolbar, belowToolbar, children, ...header }: ListPageProps) {
  return (
    <PageShell width="fluid" data-template="list">
      <PageHeader {...header} />
      {toolbar ? <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">{toolbar}</div> : null}
      {belowToolbar}
      <div className="min-w-0">{children}</div>
    </PageShell>
  );
}
