"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { clearTokens } from "@/lib/auth/storage";

import { useDashboard } from "./dashboard-context";

export function UserMenu() {
  const { user } = useDashboard();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || user.email;
  const initials =
    `${user.firstName?.[0] ?? ""}${user.lastName?.[0] ?? ""}`.toUpperCase() ||
    user.email.slice(0, 2).toUpperCase();

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

  const logout = () => {
    clearTokens();
    setOpen(false);
    router.push("/login");
  };

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="flex items-center gap-2 rounded-lg p-1.5 pr-2 text-left transition hover:bg-slate-100"
        aria-expanded={open}
        aria-controls={menuId}
        aria-haspopup="menu"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="bg-brand/15 text-brand flex size-8 items-center justify-center rounded-full text-xs font-semibold">
          {initials}
        </span>
        <span className="hidden max-w-[9rem] truncate text-sm font-medium text-slate-800 sm:inline">
          {displayName}
        </span>
        <svg
          viewBox="0 0 20 20"
          className="hidden size-4 text-slate-400 sm:block"
          fill="currentColor"
        >
          <path d="M5.25 7.5L10 12.25 14.75 7.5" />
        </svg>
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-30 mt-2 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
        >
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="truncate text-sm font-medium text-slate-900">{displayName}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
          </div>
          <Link
            href="/dashboard/settings"
            role="menuitem"
            className="block px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50"
            onClick={() => setOpen(false)}
          >
            Hesap ayarları
          </Link>
          <button
            type="button"
            role="menuitem"
            className="block w-full px-4 py-2.5 text-left text-sm text-red-700 hover:bg-red-50"
            onClick={logout}
          >
            Çıkış yap
          </button>
        </div>
      ) : null}
    </div>
  );
}
