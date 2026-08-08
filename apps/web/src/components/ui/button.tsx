import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "outline";
export type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
};

const variantClass: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-primary-foreground hover:opacity-90 focus-visible:ring-primary/30 border-transparent",
  secondary:
    "border-border-default bg-surface-tertiary text-foreground hover:bg-surface-secondary focus-visible:ring-border-strong/50",
  outline:
    "border-border-strong bg-surface-primary text-foreground hover:bg-surface-secondary focus-visible:ring-border-strong/50",
  ghost:
    "border-transparent bg-transparent text-foreground hover:bg-surface-tertiary focus-visible:ring-border-default/40",
  danger:
    "border-transparent bg-danger text-white hover:opacity-90 focus-visible:ring-danger/30",
};

const sizeClass: Record<ButtonSize, string> = {
  sm: "h-[var(--control-height-sm)] px-3 text-xs",
  md: "h-[var(--control-height-md)] px-4 text-sm",
  lg: "h-[var(--control-height-lg)] px-5 text-sm",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    className,
    variant = "primary",
    size = "md",
    loading = false,
    disabled,
    children,
    type = "button",
    ...props
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[var(--radius-md)] border font-semibold transition focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60",
        variantClass[variant],
        sizeClass[size],
        className,
      )}
      {...props}
    >
      {loading ? (
        <span
          aria-hidden
          className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      ) : null}
      {children}
    </button>
  );
});
