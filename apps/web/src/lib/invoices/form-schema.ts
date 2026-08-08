import { z } from "zod";

/** Shared with InvoiceCreateForm — tested in NP-172 / NP-451. */
export const invoiceCreateSchema = z
  .object({
    customer: z.string().min(1, "Müşteri seçin"),
    number: z.string().min(1, "Fatura numarası gerekli"),
    invoice_date: z.string().min(1, "Fatura tarihi gerekli"),
    due_date: z.string().min(1, "Vade tarihi gerekli"),
    currency: z.string().length(3, "Para birimi 3 harf olmalı"),
    subtotal_amount: z.string().min(1, "Ara toplam gerekli"),
    tax_amount: z.string().min(1, "Vergi gerekli"),
    total_amount: z.string().min(1, "Toplam gerekli"),
    description: z.string(),
  })
  .superRefine((values, ctx) => {
    if (values.invoice_date && values.due_date && values.due_date < values.invoice_date) {
      ctx.addIssue({
        code: "custom",
        path: ["due_date"],
        message: "Vade tarihi, fatura tarihinden önce olamaz.",
      });
    }
  });

export function sumMoney(a: string, b: string): string {
  const x = Number(a);
  const y = Number(b);
  if (Number.isNaN(x) || Number.isNaN(y)) return a;
  return (x + y).toFixed(2);
}

export function addDaysISO(baseISO: string, days: number) {
  const d = new Date(`${baseISO}T12:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}
