import { cn } from "@/lib/cn";
import {
  FINANCIAL_COLOR_MEANING,
  SEMANTIC_SOFT_CLASS,
  type SemanticTone,
} from "@/lib/design/semantic";

/** NP-493 — shape + text, not color alone. */
const SHAPES: Record<SemanticTone, string> = {
  success: "✓",
  info: "◆",
  warning: "●",
  danger: "▲",
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
 * NP-371 / NP-493 — never rely on color alone: shape + text + semantic tone.
 */
export function StatusChip({ tone, label, className, meaning }: StatusChipProps) {
  const meta = FINANCIAL_COLOR_MEANING[tone];
  const shape = SHAPES[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[var(--radius-md)] px-2 py-0.5 text-xs font-semibold",
        SEMANTIC_SOFT_CLASS[tone],
        className,
      )}
      title={meaning || meta.label}
    >
      <span aria-hidden className="font-bold leading-none">
        {shape}
      </span>
      <span>{label}</span>
      <span className="sr-only">{meaning || meta.label}</span>
    </span>
  );
}
