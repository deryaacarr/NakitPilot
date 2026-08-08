/**
 * NP-500 — canonical component inventory (design consistency audit).
 * Prefer these over ad-hoc duplicates.
 */
export const COMPONENT_AUDIT = {
  button: {
    canonical: ["Button", "ButtonLink"],
    variants: 5,
    sizes: 3,
    rule: "CTA’lar Button/ButtonLink; ham <button> yalnızca ikon/toggle/tab için.",
  },
  modal: {
    canonical: ["Modal", "ConfirmDialog", "Drawer"],
    variants: 3,
    rule: "Form/onay → Modal/ConfirmDialog; yan panel → Drawer; arama/sidebar özel kalabilir.",
  },
  inputHeight: {
    canonical: ["Input", "Select", "Textarea"],
    heights: ["--control-height-sm", "--control-height-md", "--control-height-lg"],
    rule: "Tek yükseklik kaynağı tokens.css; Textarea dikey min-height kullanır.",
  },
  card: {
    canonical: ["Surface", "np-surface", "np-surface-muted"],
    variants: 2,
    rule: "Panel/kart sarmalayıcı Surface; domain kartları (TaskCard/KPI) Surface üzerine kurulur.",
  },
  badge: {
    canonical: ["Badge", "StatusChip"],
    variants: 2,
    rule: "Sayım/etiket → Badge; risk/durum (şekil+metin) → StatusChip.",
  },
} as const;

export const AUDIT_SUMMARY_ROWS = [
  {
    category: "Buton",
    count: "1 sistem · 5 variant · 3 size",
    canonical: "Button / ButtonLink",
  },
  {
    category: "Modal / overlay",
    count: "3 primitive",
    canonical: "Modal · ConfirmDialog · Drawer",
  },
  {
    category: "Input yüksekliği",
    count: "3 token",
    canonical: "--control-height-sm/md/lg",
  },
  {
    category: "Kart / surface",
    count: "2 tone",
    canonical: "Surface (default | muted)",
  },
  {
    category: "Badge",
    count: "2 bileşen",
    canonical: "Badge · StatusChip",
  },
] as const;
