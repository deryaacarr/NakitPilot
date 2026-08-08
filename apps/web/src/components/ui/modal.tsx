"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { useFocusTrap } from "@/lib/a11y/use-focus-trap";
import { cn } from "@/lib/cn";

import { Button } from "./button";

export type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  className?: string;
};

const sizeClass = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
};

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  className,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
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

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Kapat"
        className="absolute inset-0 bg-foreground/40"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ui-modal-title"
        tabIndex={-1}
        className={cn(
          "relative z-10 w-full rounded-[var(--radius-lg)] border border-border-default bg-surface-primary shadow-[var(--shadow-lg)] outline-none",
          sizeClass[size],
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border-default px-5 py-4">
          <div className="min-w-0 space-y-1">
            <h2 id="ui-modal-title" className="text-lg font-semibold text-foreground">
              {title}
            </h2>
            {description ? <p className="text-sm text-muted">{description}</p> : null}
          </div>
          <Button variant="ghost" className="min-h-11 min-w-11" onClick={onClose} aria-label="Kapat">
            ✕
          </Button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer ? <div className="border-t border-border-default px-5 py-4">{footer}</div> : null}
      </div>
    </div>
  );
}
