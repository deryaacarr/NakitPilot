"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { getCustomer } from "@/lib/customers/api";
import { getInvoice } from "@/lib/invoices/api";

import { DASHBOARD_NAV } from "./nav-config";

export type Crumb = { href: string; label: string };

const LABEL_OVERRIDES: Record<string, string> = {
  dashboard: "Ana Sayfa",
  customers: "Müşteriler",
  invoices: "Faturalar",
  collections: "Tahsilat",
  promises: "Ödeme sözleri",
  messages: "Mesajlar",
  forecast: "Nakit akışı",
  imports: "İçe aktarma",
  reports: "Raporlar",
  settings: "Ayarlar",
  payments: "Ödemeler",
  tasks: "Tüm görevler",
  calendar: "Takvim",
  field: "Saha",
  aging: "Yaşlandırma",
  performance: "Tahsilat performansı",
  workflows: "Workflow’lar",
  "risk-monitoring": "Risk analizi",
  new: "Yeni",
  edit: "Düzenle",
  legal: "Hukuki",
  platform: "Platform",
  notifications: "Bildirimler",
};

function titleCaseSegment(segment: string) {
  return LABEL_OVERRIDES[segment] ?? segment.replace(/-/g, " ");
}

function isId(segment: string) {
  return /^\d+$/.test(segment);
}

/** NP-383 — hierarchical breadcrumbs with entity labels */
export function Breadcrumb() {
  const pathname = usePathname();
  const [resolved, setResolved] = useState<Crumb[]>([]);

  const structural = useMemo(() => {
    const parts = pathname.split("/").filter(Boolean);
    if (parts.length === 0) return [{ href: "/dashboard", label: "Ana Sayfa" }];

    const items: Crumb[] = [];
    let acc = "";
    for (const part of parts) {
      acc += `/${part}`;
      const navMatch = DASHBOARD_NAV.find((n) => n.href.split("#")[0] === acc);
      items.push({
        href: acc,
        label: navMatch?.label ?? (isId(part) ? part : titleCaseSegment(part)),
      });
    }
    return items;
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;
    const parts = pathname.split("/").filter(Boolean);

    async function enrich() {
      const crumbs = [...structural];

      // /customers/:id...
      if (parts[0] === "customers" && parts[1] && isId(parts[1])) {
        const res = await getCustomer(parts[1]);
        if (!cancelled && res.ok) {
          const idx = crumbs.findIndex((c) => c.href === `/customers/${parts[1]}`);
          if (idx >= 0) crumbs[idx] = { ...crumbs[idx], label: res.data.name };
        }
      }

      // /invoices/:id → Müşteriler / {customer} / Faturalar / {number}
      if (parts[0] === "invoices" && parts[1] && isId(parts[1])) {
        const res = await getInvoice(parts[1]);
        if (!cancelled && res.ok) {
          const inv = res.data;
          const rebuilt: Crumb[] = [
            { href: "/customers", label: "Müşteriler" },
            { href: `/customers/${inv.customer}`, label: inv.customer_name || `Müşteri #${inv.customer}` },
            { href: "/invoices", label: "Faturalar" },
            { href: `/invoices/${inv.id}`, label: inv.number },
          ];
          if (parts[2] === "edit") {
            rebuilt.push({ href: `/invoices/${inv.id}/edit`, label: "Düzenle" });
          }
          setResolved(rebuilt);
          return;
        }
      }

      if (!cancelled) setResolved(crumbs);
    }

    void enrich();
    return () => {
      cancelled = true;
    };
  }, [pathname, structural]);

  const crumbs = resolved.length ? resolved : structural;
  const mobileCrumbs =
    crumbs.length <= 2
      ? crumbs
      : [{ href: crumbs[crumbs.length - 2].href, label: "…" }, crumbs[crumbs.length - 1]];

  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="hidden items-center gap-1.5 text-sm text-muted sm:flex">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li key={`${crumb.href}-${index}`} className="flex min-w-0 items-center gap-1.5">
              {index > 0 ? <span aria-hidden className="text-border-strong">/</span> : null}
              {isLast ? (
                <span className="truncate font-medium text-foreground" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <Link href={crumb.href} className="truncate hover:text-foreground">
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
      <ol className="flex items-center gap-1.5 text-sm text-muted sm:hidden">
        {mobileCrumbs.map((crumb, index) => {
          const isLast = index === mobileCrumbs.length - 1;
          return (
            <li key={`m-${crumb.href}-${index}`} className="flex min-w-0 items-center gap-1.5">
              {index > 0 ? <span aria-hidden className="text-border-strong">/</span> : null}
              {isLast ? (
                <span className="truncate font-medium text-foreground" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <Link href={crumb.href} className="truncate hover:text-foreground">
                  {crumb.label === "…" ? "Geri" : crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
