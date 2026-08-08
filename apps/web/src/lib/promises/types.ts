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
  paid_amount?: string;
  remaining_amount?: string;
  delay_days?: number;
  assigned_to?: number | null;
  assigned_to_name?: string | null;
  assigned_to_email?: string | null;
};

export type PromiseCalendar = {
  today: PaymentPromise[];
  upcoming: PaymentPromise[];
  broken: PaymentPromise[];
  fulfilled: PaymentPromise[];
};

export type PromiseStatusBoard = {
  pending: PaymentPromise[];
  today: PaymentPromise[];
  upcoming: PaymentPromise[];
  partial: PaymentPromise[];
  fulfilled: PaymentPromise[];
  broken: PaymentPromise[];
};

export type PromiseBoardKey = keyof PromiseStatusBoard;

export const PROMISE_STATUS_LABELS: Record<string, string> = {
  PENDING: "Bekliyor",
  PARTIALLY_FULFILLED: "Kısmi karşılandı",
  FULFILLED: "Karşılandı",
  BROKEN: "Bozuldu",
  CANCELLED: "İptal",
};

export const PROMISE_BOARD_GROUPS: {
  key: PromiseBoardKey;
  title: string;
  tone: "neutral" | "brand" | "warning" | "analysis" | "success" | "danger";
}[] = [
  { key: "pending", title: "Bekliyor", tone: "neutral" },
  { key: "today", title: "Bugün", tone: "brand" },
  { key: "upcoming", title: "Yaklaşıyor", tone: "warning" },
  { key: "partial", title: "Kısmi karşılandı", tone: "analysis" },
  { key: "fulfilled", title: "Karşılandı", tone: "success" },
  { key: "broken", title: "Bozuldu", tone: "danger" },
];
