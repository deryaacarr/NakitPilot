import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export type SelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  hint?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
};

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, label, hint, error, id, options, placeholder, disabled, ...props },
  ref,
) {
  const selectId = id ?? props.name;
  const errorId = selectId ? `${selectId}-error` : undefined;
  const hintId = selectId ? `${selectId}-hint` : undefined;

  return (
    <div className="space-y-1.5">
      {label ? (
        <label htmlFor={selectId} className="block text-sm font-medium text-foreground">
          {label}
        </label>
      ) : null}
      <select
        ref={ref}
        id={selectId}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        className={cn(
          "h-[var(--control-height-md)] w-full rounded-[var(--radius-md)] border bg-surface-primary px-3 text-sm text-foreground transition outline-none focus:ring-2 disabled:cursor-not-allowed disabled:bg-surface-secondary disabled:opacity-70",
          error
            ? "border-danger focus:border-danger focus:ring-danger/20"
            : "border-border-default focus:border-primary focus:ring-primary/20",
          className,
        )}
        {...props}
      >
        {placeholder ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
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
