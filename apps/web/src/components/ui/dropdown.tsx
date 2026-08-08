"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export type DropdownItem = {
  id: string;
  label: string;
  onSelect?: () => void;
  href?: string;
  danger?: boolean;
  disabled?: boolean;
};

export type DropdownProps = {
  trigger: ReactNode;
  items: DropdownItem[];
  align?: "left" | "right";
  className?: string;
};

export function Dropdown({ trigger, items, align = "right", className }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className={cn("relative inline-flex", className)} ref={rootRef}>
      <div
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setOpen((value) => !value);
          }
        }}
        role="button"
        tabIndex={0}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
      >
        {trigger}
      </div>
      {open ? (
        <div
          id={menuId}
          role="menu"
          className={cn(
            "absolute z-30 mt-2 min-w-48 overflow-hidden rounded-[var(--radius-lg)] border border-border-default bg-surface-primary py-1 shadow-[var(--shadow-lg)]",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {items.map((item) => {
            const itemClass = cn(
              "block w-full min-h-11 px-3 py-2.5 text-left text-sm transition",
              item.danger
                ? "text-danger-foreground hover:bg-danger-soft"
                : "text-foreground hover:bg-surface-secondary",
              item.disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
            );

            if (item.href && !item.disabled) {
              return (
                <a
                  key={item.id}
                  href={item.href}
                  role="menuitem"
                  className={itemClass}
                  onClick={() => {
                    item.onSelect?.();
                    setOpen(false);
                  }}
                >
                  {item.label}
                </a>
              );
            }

            return (
              <button
                key={item.id}
                type="button"
                role="menuitem"
                disabled={item.disabled}
                className={itemClass}
                onClick={() => {
                  item.onSelect?.();
                  setOpen(false);
                }}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
