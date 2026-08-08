"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { useFocusTrap } from "@/lib/a11y/use-focus-trap";
import { cn } from "@/lib/cn";

import { Button } from "./button";

export type DrawerProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  side?: "left" | "right";
  footer?: ReactNode;
  className?: string;
};

export function Drawer({
  open,
  onClose,
  title,
  children,
  side = "right",
  footer,
  className,
}: DrawerProps) {
  const panelRef = useRef<HTMLElement>(null);
  useFocusTrap(panelRef, open);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  return (
    <div className={cn("fixed inset-0 z-50", open ? "pointer-events-auto" : "pointer-events-none")}>
      <button
        type="button"
        aria-label="Kapat"
        className={cn(
          "absolute inset-0 bg-foreground/40 transition-opacity",
          open ? "opacity-100" : "opacity-0",
        )}
        onClick={onClose}
      />
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          "absolute inset-y-0 flex w-[min(24rem,92vw)] flex-col bg-surface-primary shadow-[var(--shadow-lg)] outline-none transition-transform duration-200",
          side === "right" ? "right-0" : "left-0",
          open ? "translate-x-0" : side === "right" ? "translate-x-full" : "-translate-x-full",
          className,
        )}
      >
        <div className="flex items-center justify-between border-b border-border-default px-4 py-3">
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
          <Button variant="ghost" className="min-h-11 min-w-11" onClick={onClose} aria-label="Kapat">
            ✕
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4">{children}</div>
        {footer ? <div className="border-t border-border-default px-4 py-3">{footer}</div> : null}
      </aside>
    </div>
  );
}
