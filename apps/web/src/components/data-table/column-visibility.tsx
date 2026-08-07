"use client";

import { cn } from "@/lib/cn";

import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/dropdown";

type ColumnVisibilityMenuProps = {
  columns: Array<{ id: string; header: string; hideable?: boolean }>;
  hiddenColumnIds: string[];
  onChange: (ids: string[]) => void;
};

export function ColumnVisibilityMenu({
  columns,
  hiddenColumnIds,
  onChange,
}: ColumnVisibilityMenuProps) {
  const hideable = columns.filter((c) => c.hideable !== false);

  if (hideable.length === 0) return null;

  return (
    <Dropdown
      align="right"
      trigger={
        <Button type="button" variant="outline" size="sm">
          Kolonlar
        </Button>
      }
      items={hideable.map((column) => {
        const hidden = hiddenColumnIds.includes(column.id);
        return {
          id: column.id,
          label: `${hidden ? "□" : "☑"} ${column.header}`,
          onSelect: () => {
            if (hidden) {
              onChange(hiddenColumnIds.filter((id) => id !== column.id));
            } else {
              // En az bir kolon görünür kalsın
              if (hideable.length - hiddenColumnIds.length <= 1) return;
              onChange([...hiddenColumnIds, column.id]);
            }
          },
        };
      })}
    />
  );
}

export function SortIndicator({
  active,
  direction,
}: {
  active: boolean;
  direction?: "asc" | "desc";
}) {
  return (
    <span
      className={cn("ml-1 inline-block text-[10px] text-slate-400", active && "text-brand")}
      aria-hidden
    >
      {!active ? "↕" : direction === "asc" ? "↑" : "↓"}
    </span>
  );
}
