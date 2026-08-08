import type { ReactNode } from "react";

import { PageHeader, type PageHeaderProps } from "./page-header";
import { PageShell } from "./page-shell";
import { Surface } from "@/components/ui/surface";
import { cn } from "@/lib/cn";

export type WizardStep = {
  id: string;
  label: string;
};

export type WizardPageProps = PageHeaderProps & {
  steps: WizardStep[];
  activeStepId: string;
  children: ReactNode;
  footer?: ReactNode;
};

/** NP-501 — Wizard sayfası şablonu. */
export function WizardPage({
  steps,
  activeStepId,
  children,
  footer,
  ...header
}: WizardPageProps) {
  const activeIndex = Math.max(
    0,
    steps.findIndex((s) => s.id === activeStepId),
  );

  return (
    <PageShell width="wizard" data-template="wizard">
      <PageHeader {...header} />
      <ol className="flex flex-wrap gap-2">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={cn(
              "inline-flex min-h-11 items-center rounded-[var(--radius-md)] px-3 text-sm font-medium",
              index === activeIndex
                ? "bg-primary/10 text-primary"
                : index < activeIndex
                  ? "bg-primary/10 text-primary"
                  : "bg-surface-secondary text-muted",
            )}
          >
            <span className="mr-2 tabular-nums" aria-hidden>
              {index + 1}.
            </span>
            {step.label}
          </li>
        ))}
      </ol>
      <Surface as="section">{children}</Surface>
      {footer ? <div className="flex flex-wrap justify-end gap-2">{footer}</div> : null}
    </PageShell>
  );
}
