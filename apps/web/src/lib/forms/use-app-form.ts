"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  useForm,
  type DefaultValues,
  type FieldValues,
  type UseFormProps,
  type UseFormReturn,
} from "react-hook-form";
import type { z } from "zod";

import { useUnsavedChangesWarning } from "./use-unsaved-changes";

type AppFormOptions<TValues extends FieldValues> = Omit<
  UseFormProps<TValues>,
  "resolver" | "defaultValues"
> & {
  schema: z.ZodType<TValues>;
  defaultValues: DefaultValues<TValues>;
  /** true ise dirty iken beforeunload uyarısı (varsayılan: true) */
  warnUnsavedChanges?: boolean;
};

/**
 * RHF + Zod resolver + kaydedilmemiş değişiklik uyarısı (NP-033).
 */
export function useAppForm<TValues extends FieldValues>(
  options: AppFormOptions<TValues>,
): UseFormReturn<TValues> {
  const { schema, defaultValues, warnUnsavedChanges = true, ...rest } = options;

  const form = useForm<TValues>({
    // NP-451 — validate inline on blur; revalidate as user fixes fields.
    mode: "onBlur",
    reValidateMode: "onChange",
    ...rest,
    // zodResolver generics vary across Zod major versions; schema is validated at runtime.
    resolver: zodResolver(schema as never),
    defaultValues,
  });

  useUnsavedChangesWarning(warnUnsavedChanges && form.formState.isDirty);

  return form;
}
