import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  hint?: string;
  error?: string;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, label, hint, error, id, disabled, ...props },
  ref,
) {
  const inputId = id ?? props.name;

  return (
    <div className="space-y-[var(--space-2)]">
      {label ? (
        <label htmlFor={inputId} className="block text-sm font-medium text-foreground">
          {label}
        </label>
      ) : null}
      <input
        ref={ref}
        id={inputId}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        className={cn(
          "h-[var(--control-height-md)] w-full rounded-[var(--radius-md)] border bg-surface-primary px-3 text-sm text-foreground transition outline-none placeholder:text-subtle focus:ring-2 disabled:cursor-not-allowed disabled:bg-surface-secondary disabled:opacity-70",
          error
            ? "border-danger focus:border-danger focus:ring-danger/20"
            : "border-border-default focus:border-primary focus:ring-primary/20",
          className,
        )}
        {...props}
      />
      {error ? (
        <p className="text-sm text-danger-foreground" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="np-helper">{hint}</p>
      ) : null}
    </div>
  );
});
