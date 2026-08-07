/** NP-172 — payment allocation validation (decimal-safe via string cents). */

export type AllocationLine = {
  invoiceId: number;
  amount: string;
};

function toCents(value: string): number | null {
  const cleaned = value.trim().replace(",", ".");
  if (!/^-?\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const [whole, frac = ""] = cleaned.split(".");
  const cents = Number(whole) * 100 + Number((frac + "00").slice(0, 2));
  return Number.isFinite(cents) ? cents : null;
}

export function sumAllocationAmounts(lines: AllocationLine[]): string {
  let total = 0;
  for (const line of lines) {
    const cents = toCents(line.amount);
    if (cents == null) continue;
    total += cents;
  }
  return (total / 100).toFixed(2);
}

export function validateAllocationTotals(
  paymentAmount: string,
  lines: AllocationLine[],
): { ok: true; allocated: string } | { ok: false; code: string; message: string } {
  const paymentCents = toCents(paymentAmount);
  if (paymentCents == null || paymentCents <= 0) {
    return { ok: false, code: "invalid_payment", message: "Ödeme tutarı geçersiz." };
  }
  let allocated = 0;
  for (const line of lines) {
    const cents = toCents(line.amount);
    if (cents == null || cents < 0) {
      return { ok: false, code: "invalid_line", message: "Dağıtım tutarı geçersiz." };
    }
    allocated += cents;
  }
  if (allocated > paymentCents) {
    return {
      ok: false,
      code: "over_allocated",
      message: "Dağıtım tutarı ödemeyi aşamaz.",
    };
  }
  return { ok: true, allocated: (allocated / 100).toFixed(2) };
}
