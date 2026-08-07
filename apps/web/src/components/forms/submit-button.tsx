"use client";

import { useFormContext } from "react-hook-form";

import { Button, type ButtonProps } from "@/components/ui/button";

export type SubmitButtonProps = Omit<ButtonProps, "type" | "loading"> & {
  /** Dışarıdan override; yoksa form `isSubmitting` */
  loading?: boolean;
};

/**
 * Submit sırasında otomatik kilitlenir (NP-033).
 */
export function SubmitButton({ children, loading, disabled, ...props }: SubmitButtonProps) {
  const {
    formState: { isSubmitting },
  } = useFormContext();
  const busy = loading ?? isSubmitting;

  return (
    <Button type="submit" loading={busy} disabled={disabled || busy} {...props}>
      {children}
    </Button>
  );
}
