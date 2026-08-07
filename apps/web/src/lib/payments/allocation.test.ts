import { describe, expect, it } from "vitest";

import { sumAllocationAmounts, validateAllocationTotals } from "./allocation";

describe("payment allocation", () => {
  it("sums with decimal-safe cents (0.1 + 0.2)", () => {
    expect(
      sumAllocationAmounts([
        { invoiceId: 1, amount: "0.10" },
        { invoiceId: 2, amount: "0.20" },
      ]),
    ).toBe("0.30");
  });

  it("accepts exact allocation", () => {
    const result = validateAllocationTotals("100.00", [
      { invoiceId: 1, amount: "40.00" },
      { invoiceId: 2, amount: "60.00" },
    ]);
    expect(result).toEqual({ ok: true, allocated: "100.00" });
  });

  it("rejects over-allocation", () => {
    const result = validateAllocationTotals("50.00", [{ invoiceId: 1, amount: "50.01" }]);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("over_allocated");
  });

  it("rejects invalid line amounts", () => {
    const result = validateAllocationTotals("10.00", [{ invoiceId: 1, amount: "abc" }]);
    expect(result.ok).toBe(false);
  });
});
