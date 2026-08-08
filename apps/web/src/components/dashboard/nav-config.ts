export type NavIconName =
  | "home"
  | "customers"
  | "invoices"
  | "collections"
  | "imports"
  | "reports"
  | "settings"
  | "notifications"
  | "developers"
  | "workflows"
  | "risk"
  | "payments"
  | "calendar"
  | "search";

export type NavLeaf = {
  href: string;
  label: string;
  icon: NavIconName;
  /** Exact path match only (e.g. /dashboard) */
  exact?: boolean;
};

export type NavGroup = {
  id: string;
  label: string;
  items: NavLeaf[];
};

/** NP-380 — usage-ordered information architecture */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "home",
    label: "Ana Sayfa",
    items: [{ href: "/dashboard", label: "Ana Sayfa", icon: "home", exact: true }],
  },
  {
    id: "collections",
    label: "Tahsilat",
    items: [
      { href: "/collections", label: "Günlük Çalışma", icon: "collections", exact: true },
      { href: "/collections/tasks", label: "Tüm Görevler", icon: "collections" },
      { href: "/promises", label: "Ödeme Sözleri", icon: "calendar" },
      { href: "/collections/calendar", label: "Tahsilat Takvimi", icon: "calendar" },
    ],
  },
  {
    id: "finance",
    label: "Finans",
    items: [
      { href: "/customers", label: "Müşteriler", icon: "customers" },
      { href: "/invoices", label: "Faturalar", icon: "invoices" },
      { href: "/payments", label: "Ödemeler", icon: "payments" },
      { href: "/forecast", label: "Nakit Akışı", icon: "reports" },
    ],
  },
  {
    id: "analytics",
    label: "Analiz",
    items: [
      { href: "/dashboard/risk-monitoring", label: "Risk Analizi", icon: "risk" },
      { href: "/dashboard/reports/aging", label: "Yaşlandırma", icon: "reports" },
      { href: "/dashboard/reports/performance", label: "Tahsilat Performansı", icon: "reports" },
      { href: "/dashboard/reports", label: "Raporlar", icon: "reports", exact: true },
    ],
  },
  {
    id: "automation",
    label: "Otomasyon",
    items: [
      { href: "/dashboard/workflows", label: "Workflow’lar", icon: "workflows" },
      { href: "/messages", label: "Mesaj Şablonları", icon: "collections" },
      { href: "/dashboard/settings#integrations", label: "Entegrasyonlar", icon: "imports" },
    ],
  },
  {
    id: "management",
    label: "Yönetim",
    items: [
      { href: "/dashboard/settings#users", label: "Kullanıcılar", icon: "customers" },
      { href: "/dashboard/settings", label: "Şirket Ayarları", icon: "settings", exact: true },
      { href: "/dashboard/settings#subscription", label: "Abonelik", icon: "settings" },
    ],
  },
];

/** Secondary / power-user links (collapsed under “Diğer”) */
export const NAV_SECONDARY: NavLeaf[] = [
  { href: "/collections/field", label: "Saha (PWA)", icon: "collections" },
  { href: "/legal", label: "Hukuki", icon: "reports" },
  { href: "/notifications", label: "Bildirimler", icon: "notifications" },
  { href: "/imports", label: "İçe aktarma", icon: "imports" },
  { href: "/dashboard/platform", label: "Platform", icon: "settings" },
  { href: "/dashboard/design-system", label: "Tasarım sistemi", icon: "settings" },
];

/** Flat list for breadcrumb / active matching helpers */
export const DASHBOARD_NAV: NavLeaf[] = [
  ...NAV_GROUPS.flatMap((g) => g.items),
  ...NAV_SECONDARY,
];

export type NavItem = NavLeaf;

export function isNavActive(
  pathname: string,
  item: NavLeaf,
  hash = "",
): boolean {
  const [pathOnly = item.href, fragment = ""] = item.href.split("#");
  const normalizedHash = hash.replace(/^#/, "");

  if (pathOnly === "/dashboard") {
    return pathname === "/dashboard";
  }

  const pathMatch =
    item.exact
      ? pathname === pathOnly
      : pathname === pathOnly || pathname.startsWith(`${pathOnly}/`);

  if (!pathMatch) return false;

  // Hash targets (e.g. /dashboard/settings#subscription) — only one active at a time
  if (fragment) {
    return normalizedHash === fragment;
  }

  // Plain /dashboard/settings — active only when no section hash is selected
  if (item.exact && pathOnly === "/dashboard/settings") {
    return !normalizedHash;
  }

  return true;
}

/** NP-381 — quick create actions (most frequent first) */
export const QUICK_CREATE_ACTIONS = [
  { id: "customer", label: "Yeni müşteri", href: "/customers/new", shortcut: "c" },
  { id: "invoice", label: "Yeni fatura", href: "/invoices/new", shortcut: "f" },
  { id: "payment", label: "Yeni ödeme", href: "/payments/new", shortcut: "o" },
  { id: "task", label: "Yeni tahsilat görevi", href: "/collections/tasks?create=1", shortcut: "t" },
  { id: "promise", label: "Yeni ödeme sözü", href: "/promises?create=1", shortcut: "s" },
  { id: "import", label: "Yeni import", href: "/imports", shortcut: "i" },
] as const;
