import { cn } from "@/lib/cn";

type MoneyProps = {
  value: string | number | null | undefined;
  currency?: string;
  className?: string;
  size?: "body" | "metric" | "table";
};

/**
 * NP-372 — financial amount with tabular nums; currency de-emphasized.
 */
export function Money({ value, currency = "TRY", className, size = "body" }: MoneyProps) {
  const amount = typeof value === "number" ? value : Number(value ?? NaN);
  if (Number.isNaN(amount)) {
    return <span className={cn("np-helper", className)}>—</span>;
  }

  const formatted = new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);

  const currencyLabel = currency === "TRY" ? "TL" : currency;

  return (
    <span
      className={cn(
        "np-money inline-flex items-baseline",
        size === "metric" && "np-metric",
        size === "table" && "np-table-text",
        size === "body" && "text-[length:var(--text-body)] font-semibold",
        className,
      )}
      data-tabular="true"
    >
      <span>{formatted}</span>
      <span className="np-money__currency">{currencyLabel}</span>
    </span>
  );
}
