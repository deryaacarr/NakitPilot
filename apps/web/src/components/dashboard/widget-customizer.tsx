"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  WIDGET_CATALOG,
  type WidgetId,
  defaultVisibleWidgets,
  saveWidgetPrefs,
} from "@/lib/dashboard/widgets";

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

  function toggle(id: WidgetId) {
    setDraft((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  function apply() {
    const next = draft.length ? draft : defaultVisibleWidgets(persona);
    saveWidgetPrefs(persona, next);
    onChange(next);
    setOpen(false);
  }

  return (
    <div className="relative">
      <Button type="button" size="sm" variant="secondary" onClick={() => setOpen((v) => !v)}>
        Widget’lar
      </Button>
      {open ? (
        <div className="absolute right-0 z-30 mt-2 w-72 rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-3 shadow-[var(--shadow-md)]">
          <p className="text-xs font-semibold uppercase tracking-wide text-subtle">Gösterilecek paneller</p>
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
            <Button type="button" size="sm" onClick={apply}>
              Uygula
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
              Kapat
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
