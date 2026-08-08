/**
 * NP-371 — financial color meanings (single mapping, no reuse across meanings).
 */

export const FINANCIAL_COLOR_MEANING = {
  success: {
    key: "success",
    label: "Tahsil edildi / düşük risk",
    color: "green",
    css: "var(--color-success)",
  },
  info: {
    key: "info",
    label: "Bilgilendirme / normal durum",
    color: "blue",
    css: "var(--color-info)",
  },
  warning: {
    key: "warning",
    label: "Yaklaşan vade / orta risk",
    color: "orange",
    css: "var(--color-warning)",
  },
  danger: {
    key: "danger",
    label: "Gecikmiş / kritik risk",
    color: "red",
    css: "var(--color-danger)",
  },
  analysis: {
    key: "analysis",
    label: "Tahmin / yapay zekâ / analiz",
    color: "purple",
    css: "var(--color-analysis)",
  },
  neutral: {
    key: "neutral",
    label: "Pasif / tamamlanmış / nötr",
    color: "gray",
    css: "var(--color-neutral)",
  },
} as const;

export type SemanticTone = keyof typeof FINANCIAL_COLOR_MEANING;

/** Map domain risk/status strings → semantic tone */
export function toneFromRisk(risk: string | null | undefined): SemanticTone {
  const value = (risk || "").toUpperCase();
  if (value === "LOW" || value === "COLLECTED" || value === "PAID" || value === "FULFILLED") {
    return "success";
  }
  if (value === "MEDIUM" || value === "DUE_SOON" || value === "PENDING") {
    return "warning";
  }
  if (value === "HIGH" || value === "CRITICAL" || value === "OVERDUE" || value === "BROKEN") {
    return "danger";
  }
  if (value === "FORECAST" || value === "AI" || value === "ANALYSIS") {
    return "analysis";
  }
  if (value === "COMPLETED" || value === "CANCELLED" || value === "CLOSED") {
    return "neutral";
  }
  return "info";
}

export const SEMANTIC_SOFT_CLASS: Record<SemanticTone, string> = {
  success: "bg-success-soft text-success-foreground",
  info: "bg-info-soft text-info-foreground",
  warning: "bg-warning-soft text-warning-foreground",
  danger: "bg-danger-soft text-danger-foreground",
  analysis: "bg-analysis-soft text-analysis-foreground",
  neutral: "bg-neutral-soft text-neutral-foreground",
};

export const SEMANTIC_DOT_CLASS: Record<SemanticTone, string> = {
  success: "bg-success",
  info: "bg-info",
  warning: "bg-warning",
  danger: "bg-danger",
  analysis: "bg-analysis",
  neutral: "bg-neutral",
};
