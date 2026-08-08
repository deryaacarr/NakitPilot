import { forwardRef, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  hint?: string;
  error?: string;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, label, hint, error, id, disabled, rows = 4, ...props },
  ref,
) {
  const textareaId = id ?? props.name;
  const errorId = textareaId ? `${textareaId}-error` : undefined;
  const hintId = textareaId ? `${textareaId}-hint` : undefined;

  return (
    <div className="space-y-[var(--space-2)]">
      {label ? (
        <label htmlFor={textareaId} className="block text-sm font-medium text-foreground">
          {label}
        </label>
      ) : null}
      <textarea
        ref={ref}
        id={textareaId}
        rows={rows}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        className={cn(
          "min-h-[6.5rem] w-full rounded-[var(--radius-md)] border bg-surface-primary px-3 py-2 text-sm text-foreground transition outline-none placeholder:text-subtle focus:ring-2 disabled:cursor-not-allowed disabled:bg-surface-secondary disabled:opacity-70",
          error
            ? "border-danger focus:border-danger focus:ring-danger/20"
            : "border-border-default focus:border-primary focus:ring-primary/20",
          className,
        )}
        {...props}
      />
      {error ? (
        <p id={errorId} className="text-sm text-danger-foreground" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="np-helper">
          {hint}
        </p>
      ) : null}
    </div>
  );
});
