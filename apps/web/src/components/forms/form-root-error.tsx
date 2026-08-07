"use client";

import { useFormContext } from "react-hook-form";

import { cn } from "@/lib/cn";

export type FormRootErrorProps = {
  className?: string;
  /** Varsayılan: root.server */
  name?: string;
};

export function FormRootError({ className, name = "root.server" }: FormRootErrorProps) {
  const {
    formState: { errors },
  } = useFormContext();

  const parts = name.split(".");
  let node: unknown = errors;
  for (const part of parts) {
    if (!node || typeof node !== "object") {
      node = null;
      break;
    }
    node = (node as Record<string, unknown>)[part];
  }

  const message =
    node && typeof node === "object" && "message" in node
      ? String((node as { message?: unknown }).message ?? "")
      : "";

  if (!message) return null;

  return (
    <div
      role="alert"
      className={cn(
        "rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800",
        className,
      )}
    >
      {message}
    </div>
  );
}
