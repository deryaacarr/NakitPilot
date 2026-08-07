import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useDataTableState } from "./use-data-table-state";

type Row = { name: string; city: string };

const columns = [
  { id: "name", header: "Ad", cell: (row: Row) => row.name },
  { id: "city", header: "Şehir", cell: (row: Row) => row.city, defaultHidden: true },
];

describe("useDataTableState filters", () => {
  it("resets page when search or filter changes", () => {
    const { result } = renderHook(() =>
      useDataTableState({ columns, initialPageSize: 10, initialSort: null }),
    );

    act(() => result.current.setPage(3));
    expect(result.current.page).toBe(3);

    act(() => result.current.setSearch("acme"));
    expect(result.current.search).toBe("acme");
    expect(result.current.page).toBe(1);

    act(() => result.current.setPage(2));
    act(() => result.current.setFilter("city", "İstanbul"));
    expect(result.current.filters.city).toBe("İstanbul");
    expect(result.current.page).toBe(1);
  });

  it("cycles sort asc → desc → none", () => {
    const { result } = renderHook(() => useDataTableState({ columns }));
    act(() => result.current.toggleSort("name"));
    expect(result.current.sort).toEqual({ id: "name", direction: "asc" });
    act(() => result.current.toggleSort("name"));
    expect(result.current.sort).toEqual({ id: "name", direction: "desc" });
    act(() => result.current.toggleSort("name"));
    expect(result.current.sort).toBeNull();
  });

  it("starts with defaultHidden columns", () => {
    const { result } = renderHook(() => useDataTableState({ columns }));
    expect(result.current.hiddenColumnIds).toEqual(["city"]);
  });
});
