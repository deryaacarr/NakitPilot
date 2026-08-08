import type { ReactNode } from "react";

import { PageHeader, type PageHeaderProps } from "./page-header";
import { PageShell } from "./page-shell";

export type DashboardPageProps = PageHeaderProps & {
  /** KPI strip */
  metrics?: ReactNode;
  children: ReactNode;
};

/** NP-501 — Dashboard sayfası şablonu. */
export function DashboardPage({ metrics, children, ...header }: DashboardPageProps) {
  return (
    <PageShell width="fluid" data-template="dashboard">
      <PageHeader {...header} />
      {metrics ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{metrics}</div>
      ) : null}
      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">{children}</div>
    </PageShell>
  );
}
