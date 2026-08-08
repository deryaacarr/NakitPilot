import { cn } from "@/lib/cn";
import { SEMANTIC_SOFT_CLASS, type SemanticTone } from "@/lib/design/semantic";

export type BadgeTone = SemanticTone | "brand";

export type BadgeProps = {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
};

const toneClass: Record<BadgeTone, string> = {
  ...SEMANTIC_SOFT_CLASS,
  brand: "bg-primary/15 text-primary",
  // Map legacy alias used in older call sites
  // success/warning/danger/neutral already covered
};

export function Badge({ children, tone = "neutral", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[var(--radius-md)] px-2 py-0.5 text-xs font-semibold",
        toneClass[tone] ?? SEMANTIC_SOFT_CLASS.neutral,
        className,
      )}
    >
      {children}
    </span>
  );
}
