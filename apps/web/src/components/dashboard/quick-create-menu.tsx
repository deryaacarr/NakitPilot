"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

import { QUICK_CREATE_ACTIONS } from "./nav-config";

export function QuickCreateMenu() {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === "n") {
        event.preventDefault();
        setOpen(true);
        return;
      }
      if (!open) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      const action = QUICK_CREATE_ACTIONS.find((a) => a.shortcut === event.key.toLowerCase());
      if (action && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        window.location.href = action.href;
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={rootRef}>
      <Button
        size="sm"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        title="Hızlı işlem (Ctrl/⌘+Shift+N)"
      >
        + Yeni
      </Button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-40 mt-2 w-64 overflow-hidden rounded-[var(--radius-lg)] border border-border-default bg-surface-primary py-1 shadow-[var(--shadow-md)]"
        >
          <p className="px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-subtle">
            Hızlı işlem
          </p>
          {QUICK_CREATE_ACTIONS.map((action) => (
            <Link
              key={action.id}
              href={action.href}
              role="menuitem"
              className="flex items-center justify-between px-3 py-2 text-sm text-foreground hover:bg-surface-tertiary"
              onClick={() => setOpen(false)}
            >
              <span>{action.label}</span>
              <kbd className="rounded border border-border-default px-1.5 text-[10px] text-subtle">
                {action.shortcut.toUpperCase()}
              </kbd>
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  );
}
