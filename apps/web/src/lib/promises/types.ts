export type PaymentPromise = {
  id: number;
  customer: number;
  customer_name: string;
  invoice: number | null;
  invoice_number?: string | null;
  promised_date: string;
  amount: string;
  currency: string;
  status: string;
  notes: string;
  created_at: string;
};

export type PromiseCalendar = {
  today: PaymentPromise[];
  upcoming: PaymentPromise[];
  broken: PaymentPromise[];
  fulfilled: PaymentPromise[];
};

export const PROMISE_STATUS_LABELS: Record<string, string> = {
  PENDING: "Bekliyor",
  PARTIALLY_FULFILLED: "Kısmi",
  FULFILLED: "Karşılandı",
  BROKEN: "Bozuldu",
  CANCELLED: "İptal",
};
