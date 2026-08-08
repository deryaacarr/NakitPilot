import { cn } from "@/lib/cn";
import {
  FINANCIAL_COLOR_MEANING,
  SEMANTIC_DOT_CLASS,
  SEMANTIC_SOFT_CLASS,
  type SemanticTone,
} from "@/lib/design/semantic";

const ICONS: Record<SemanticTone, string> = {
  success: "✓",
  info: "i",
  warning: "!",
  danger: "‼",
  analysis: "◇",
  neutral: "–",
};

type StatusChipProps = {
  tone: SemanticTone;
  label: string;
  className?: string;
  /** Optional explicit meaning hint for a11y (defaults to financial mapping) */
  meaning?: string;
};

/**
 * NP-371 — never rely on color alone: icon + text + semantic tone.
 */
export function StatusChip({ tone, label, className, meaning }: StatusChipProps) {
  const meta = FINANCIAL_COLOR_MEANING[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[var(--radius-md)] px-2 py-0.5 text-xs font-semibold",
        SEMANTIC_SOFT_CLASS[tone],
        className,
      )}
      title={meaning || meta.label}
    >
      <span
        aria-hidden
        className={cn(
          "inline-flex size-3.5 items-center justify-center rounded-full text-[9px] font-bold text-white",
          SEMANTIC_DOT_CLASS[tone],
        )}
      >
        {ICONS[tone]}
      </span>
      <span>{label}</span>
      <span className="sr-only">{meaning || meta.label}</span>
    </span>
  );
}
