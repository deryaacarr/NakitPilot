"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/cn";

const ITEMS = [
  { id: "home", href: "/dashboard", label: "Ana Sayfa", icon: "⌂", exact: true },
  { id: "tasks", href: "/collections", label: "Görevler", icon: "☰", exact: false },
  { id: "search", href: "#search", label: "Ara", icon: "⌕", exact: false },
  { id: "notifications", href: "/notifications", label: "Bildirimler", icon: "◉", exact: false },
  { id: "profile", href: "/dashboard/settings", label: "Profil", icon: "☺", exact: false },
] as const;

/** NP-481 — mobile bottom navigation. */
export function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Mobil alt menü"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border-default bg-surface-primary/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
    >
      <ul className="grid grid-cols-5">
        {ITEMS.map((item) => {
          const active =
            item.id === "search"
              ? false
              : item.exact
                ? pathname === item.href
                : pathname === item.href || pathname.startsWith(`${item.href}/`);

          if (item.id === "search") {
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => window.dispatchEvent(new CustomEvent("nakitpilot:open-search"))}
                  className="flex min-h-14 w-full flex-col items-center justify-center gap-0.5 px-1 text-[10px] font-semibold text-muted"
                  aria-label="Ara"
                >
                  <span className="text-lg leading-none" aria-hidden>
                    {item.icon}
                  </span>
                  {item.label}
                </button>
              </li>
            );
          }

          return (
            <li key={item.id}>
              <Link
                href={item.href}
                className={cn(
                  "flex min-h-14 w-full flex-col items-center justify-center gap-0.5 px-1 text-[10px] font-semibold",
                  active ? "text-primary" : "text-muted",
                )}
                aria-current={active ? "page" : undefined}
              >
                <span className="text-lg leading-none" aria-hidden>
                  {item.icon}
                </span>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
