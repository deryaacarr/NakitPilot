"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type AutosaveStatus = "idle" | "saving" | "saved" | "error";

type Options<T> = {
  value: T;
  /** Persist function; throw or return { ok: false } on failure. */
  save: (value: T) => Promise<void | { ok: boolean; message?: string }>;
  debounceMs?: number;
  enabled?: boolean;
  /** Serialize for equality / storage keying */
  serialize?: (value: T) => string;
};

/**
 * NP-452 — debounce autosave with Kaydediliyor / error states; keeps latest value on failure.
 */
export function useAutosave<T>({
  value,
  save,
  debounceMs = 800,
  enabled = true,
  serialize = (v) => JSON.stringify(v),
}: Options<T>) {
  const [status, setStatus] = useState<AutosaveStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const lastSaved = useRef<string | null>(null);
  const latestValue = useRef(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveRef = useRef(save);
  saveRef.current = save;
  latestValue.current = value;

  const flush = useCallback(async () => {
    if (!enabled) return;
    const serialized = serialize(latestValue.current);
    if (serialized === lastSaved.current) return;
    setStatus("saving");
    setErrorMessage(null);
    try {
      const result = await saveRef.current(latestValue.current);
      if (result && typeof result === "object" && "ok" in result && !result.ok) {
        setStatus("error");
        setErrorMessage(result.message || "Kayıt başarısız");
        return;
      }
      lastSaved.current = serialize(latestValue.current);
      setStatus("saved");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Kayıt başarısız");
    }
  }, [enabled, serialize]);

  useEffect(() => {
    if (!enabled) return;
    const serialized = serialize(value);
    if (lastSaved.current === null) {
      lastSaved.current = serialized;
      return;
    }
    if (serialized === lastSaved.current) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      void flush();
    }, debounceMs);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [value, enabled, debounceMs, serialize, flush]);

  return { status, errorMessage, flush, setStatus };
}
