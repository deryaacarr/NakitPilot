import type { HTMLAttributes, ReactNode } from "react";

import { CONTENT_WIDTH } from "@/lib/ui/breakpoints";
import { cn } from "@/lib/cn";

export type PageWidth = keyof typeof CONTENT_WIDTH;

export type PageShellProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  width?: PageWidth;
};

export function PageShell({
  children,
  width = "fluid",
  className,
  ...props
}: PageShellProps) {
  return (
    <div className={cn("mx-auto w-full space-y-5", CONTENT_WIDTH[width], className)} {...props}>
      {children}
    </div>
  );
}
