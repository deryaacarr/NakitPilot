"use client";

import { useEffect, useState } from "react";

import { AutosaveIndicator } from "@/components/forms";
import { Button } from "@/components/ui/button";
import {
  WIDGET_CATALOG,
  type WidgetId,
  defaultVisibleWidgets,
  saveWidgetPrefs,
} from "@/lib/dashboard/widgets";
import { useAutosave } from "@/lib/forms/use-autosave";

export function WidgetCustomizer({
  persona,
  visible,
  onChange,
}: {
  persona: "manager" | "agent";
  visible: WidgetId[];
  onChange: (next: WidgetId[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(visible);

  useEffect(() => {
    setDraft(visible);
  }, [visible]);

  const catalog = WIDGET_CATALOG.filter((w) => w.roles.includes(persona));

  const autosave = useAutosave({
    value: draft,
    enabled: open,
    debounceMs: 500,
    save: async (ids) => {
      const next = ids.length ? ids : defaultVisibleWidgets(persona);
      try {
        saveWidgetPrefs(persona, next);
        onChange(next);
      } catch (err) {
        return {
          ok: false,
          message: err instanceof Error ? err.message : "Dashboard düzeni kaydedilemedi",
        };
      }
    },
  });

  function toggle(id: WidgetId) {
    setDraft((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  return (
    <div className="relative">
      <Button type="button" size="sm" variant="secondary" onClick={() => setOpen((v) => !v)}>
        Widget’lar
      </Button>
      {open ? (
        <div className="absolute right-0 z-30 mt-2 w-72 rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-3 shadow-[var(--shadow-md)]">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-subtle">
              Gösterilecek paneller
            </p>
            <AutosaveIndicator status={autosave.status} errorMessage={autosave.errorMessage} />
          </div>
          <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto">
            {catalog.map((w) => (
              <li key={w.id}>
                <label className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-surface-tertiary">
                  <input
                    type="checkbox"
                    checked={draft.includes(w.id)}
                    onChange={() => toggle(w.id)}
                  />
                  <span>{w.label}</span>
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex gap-2">
            <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
              Kapat
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
