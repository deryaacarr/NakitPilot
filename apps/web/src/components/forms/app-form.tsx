"use client";

import { FormProvider, type FieldValues, type UseFormReturn } from "react-hook-form";
import type { FormHTMLAttributes, ReactNode } from "react";

export type AppFormProps<TFieldValues extends FieldValues> = {
  form: UseFormReturn<TFieldValues>;
  onSubmit: (values: TFieldValues) => void | Promise<void>;
  children: ReactNode;
  className?: string;
} & Omit<FormHTMLAttributes<HTMLFormElement>, "onSubmit">;

/**
 * FormProvider + native form; submit sırasında RHF `handleSubmit` kullanır.
 */
export function AppForm<TFieldValues extends FieldValues>({
  form,
  onSubmit,
  children,
  className,
  ...props
}: AppFormProps<TFieldValues>) {
  return (
    <FormProvider {...form}>
      <form className={className} noValidate onSubmit={form.handleSubmit(onSubmit)} {...props}>
        {children}
      </form>
    </FormProvider>
  );
}
