import { z } from "zod";

/** Shared with InvoiceCreateForm — tested in NP-172. */
export const invoiceCreateSchema = z.object({
  customer: z.string().min(1, "Müşteri seçin"),
  number: z.string().min(1, "Fatura numarası gerekli"),
  invoice_date: z.string().min(1, "Fatura tarihi gerekli"),
  due_date: z.string().min(1, "Vade tarihi gerekli"),
  currency: z.string().length(3, "Para birimi 3 harf olmalı"),
  subtotal_amount: z.string().min(1, "Ara toplam gerekli"),
  tax_amount: z.string().min(1, "Vergi gerekli"),
  total_amount: z.string().min(1, "Toplam gerekli"),
  description: z.string(),
});

export function sumMoney(a: string, b: string): string {
  const x = Number(a);
  const y = Number(b);
  if (Number.isNaN(x) || Number.isNaN(y)) return a;
  return (x + y).toFixed(2);
}
