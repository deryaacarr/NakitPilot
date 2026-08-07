"use client";

import { useEffect } from "react";

const DEFAULT_MESSAGE =
  "Kaydedilmemiş değişiklikler var. Sayfadan ayrılmak istediğinize emin misiniz?";

/**
 * Form `isDirty` iken sekme kapatma / yenilemede tarayıcı uyarısı (NP-033).
 */
export function useUnsavedChangesWarning(isDirty: boolean, message = DEFAULT_MESSAGE): void {
  useEffect(() => {
    if (!isDirty) return;

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
      return message;
    };

    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [isDirty, message]);
}

export const UNSAVED_CHANGES_MESSAGE = DEFAULT_MESSAGE;
