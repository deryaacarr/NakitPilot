import { describe, expect, it } from "vitest";

import { invoiceCreateSchema, sumMoney } from "./form-schema";

describe("invoiceCreateSchema", () => {
  it("requires customer and amounts", () => {
    const result = invoiceCreateSchema.safeParse({
      customer: "",
      number: "",
      invoice_date: "",
      due_date: "",
      currency: "TR",
      subtotal_amount: "",
      tax_amount: "",
      total_amount: "",
      description: "",
    });
    expect(result.success).toBe(false);
  });

  it("accepts a valid payload", () => {
    const result = invoiceCreateSchema.safeParse({
      customer: "12",
      number: "INV-1",
      invoice_date: "2026-07-01",
      due_date: "2026-07-31",
      currency: "TRY",
      subtotal_amount: "100.00",
      tax_amount: "18.00",
      total_amount: "118.00",
      description: "",
    });
    expect(result.success).toBe(true);
  });
});

describe("sumMoney", () => {
  it("formats two-decimal totals", () => {
    expect(sumMoney("100.00", "18.00")).toBe("118.00");
    expect(sumMoney("0.1", "0.2")).toBe("0.30");
  });
});
