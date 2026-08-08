import type { ReactNode } from "react";

import { PageHeader, type PageHeaderProps } from "./page-header";
import { PageShell } from "./page-shell";
import { Surface } from "@/components/ui/surface";

export type ReportPageProps = PageHeaderProps & {
  /** Date range / filters */
  filters?: ReactNode;
  /** Chart / insight band */
  chart?: ReactNode;
  children: ReactNode;
};

/** NP-501 — Rapor sayfası şablonu. */
export function ReportPage({ filters, chart, children, ...header }: ReportPageProps) {
  return (
    <PageShell width="fluid" data-template="report">
      <PageHeader {...header} />
      {filters ? (
        <Surface tone="muted" className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          {filters}
        </Surface>
      ) : null}
      {chart ? <Surface as="section">{chart}</Surface> : null}
      <div className="min-w-0">{children}</div>
    </PageShell>
  );
}
