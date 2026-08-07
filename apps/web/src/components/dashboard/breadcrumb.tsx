"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";

import { DASHBOARD_NAV } from "./nav-config";

const LABEL_OVERRIDES: Record<string, string> = {
  dashboard: "Özet",
  customers: "Müşteriler",
  invoices: "Faturalar",
  collections: "Tahsilat",
  promises: "Ödeme sözleri",
  messages: "Mesajlar",
  forecast: "Nakit akışı",
  imports: "İçe aktarma",
  reports: "Raporlar",
  settings: "Ayarlar",
  new: "Yeni",
  edit: "Düzenle",
};

function titleCaseSegment(segment: string) {
  return LABEL_OVERRIDES[segment] ?? segment.replace(/-/g, " ");
}

export function Breadcrumb() {
  const pathname = usePathname();

  const crumbs = useMemo(() => {
    const parts = pathname.split("/").filter(Boolean);
    if (parts.length === 0) return [{ href: "/dashboard", label: "Özet" }];

    const items: { href: string; label: string }[] = [];
    let acc = "";
    for (const part of parts) {
      acc += `/${part}`;
      const navMatch = DASHBOARD_NAV.find((n) => n.href === acc);
      items.push({
        href: acc,
        label: navMatch?.label ?? titleCaseSegment(part),
      });
    }
    return items;
  }, [pathname]);

  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex flex-wrap items-center gap-1.5 text-sm text-slate-500">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li key={crumb.href} className="flex min-w-0 items-center gap-1.5">
              {index > 0 ? (
                <span aria-hidden className="text-slate-300">
                  /
                </span>
              ) : null}
              {isLast ? (
                <span className="truncate font-medium text-slate-800" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <Link href={crumb.href} className="truncate hover:text-slate-800">
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
