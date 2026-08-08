import type { ReactNode } from "react";

import { PageHeader, type PageHeaderProps } from "./page-header";
import { PageShell } from "./page-shell";
import { Surface } from "@/components/ui/surface";

export type FormPageProps = PageHeaderProps & {
  children: ReactNode;
  footer?: ReactNode;
  /** Side hint / autosave status */
  aside?: ReactNode;
};

/** NP-501 — Form sayfası şablonu. */
export function FormPage({ children, footer, aside, ...header }: FormPageProps) {
  return (
    <PageShell width="reading" data-template="form">
      <PageHeader {...header} />
      <div className={aside ? "grid gap-5 lg:grid-cols-[minmax(0,1fr)_16rem]" : undefined}>
        <Surface as="section" className="space-y-4">
          {children}
          {footer ? (
            <div className="flex flex-wrap justify-end gap-2 border-t border-border-default pt-4">
              {footer}
            </div>
          ) : null}
        </Surface>
        {aside ? <aside className="space-y-3 text-sm text-muted">{aside}</aside> : null}
      </div>
    </PageShell>
  );
}
