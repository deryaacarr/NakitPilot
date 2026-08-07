"use client";

import { useId, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export type TooltipProps = {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
  className?: string;
};

export function Tooltip({ content, children, side = "top", className }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const tipId = useId();

  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span aria-describedby={open ? tipId : undefined}>{children}</span>
      {open ? (
        <span
          id={tipId}
          role="tooltip"
          className={cn(
            "pointer-events-none absolute left-1/2 z-40 w-max max-w-xs -translate-x-1/2 rounded-md bg-slate-900 px-2 py-1 text-xs text-white shadow",
            side === "top" ? "bottom-[calc(100%+0.4rem)]" : "top-[calc(100%+0.4rem)]",
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}
