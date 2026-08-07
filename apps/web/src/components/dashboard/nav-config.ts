export type NavItem = {
  href: string;
  label: string;
  icon:
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
    | "risk";
};

export const DASHBOARD_NAV: NavItem[] = [
  { href: "/dashboard", label: "Özet", icon: "home" },
  { href: "/customers", label: "Müşteriler", icon: "customers" },
  { href: "/invoices", label: "Faturalar", icon: "invoices" },
  { href: "/collections", label: "Tahsilat", icon: "collections" },
  { href: "/promises", label: "Ödeme sözleri", icon: "collections" },
  { href: "/dashboard/workflows", label: "İş akışları", icon: "workflows" },
  { href: "/messages", label: "Mesajlar", icon: "collections" },
  { href: "/notifications", label: "Bildirimler", icon: "notifications" },
  { href: "/forecast", label: "Nakit akışı", icon: "reports" },
  { href: "/dashboard/risk-monitoring", label: "Model doğruluk", icon: "risk" },
  { href: "/imports", label: "İçe aktarma", icon: "imports" },
  { href: "/dashboard/reports", label: "Raporlar", icon: "reports" },
  { href: "/dashboard/developers", label: "Geliştiriciler", icon: "developers" },
  { href: "/dashboard/settings", label: "Ayarlar", icon: "settings" },
];
