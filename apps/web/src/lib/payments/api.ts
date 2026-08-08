import { apiRequest } from "@/lib/api/client";

export type Payment = {
  id: number;
  customer: number;
  customer_name: string;
  payment_date: string;
  amount: string;
  currency: string;
  method: string;
  reference: string;
  notes: string;
  unallocated_amount: string;
  is_cancelled: boolean;
  cancelled_at: string | null;
  created_at: string;
};

export type PaymentCreateInput = {
  customer: number;
  payment_date: string;
  amount: string;
  currency?: string;
  method?: string;
  reference?: string;
  notes?: string;
  auto_allocate?: boolean;
};

export type PaginatedPayments = {
  count: number;
  results: Payment[];
};

export function listPayments(query?: Record<string, string | number | boolean | null | undefined>) {
  return apiRequest<PaginatedPayments>("/api/payments/", { query });
}

export function createPayment(body: PaymentCreateInput) {
  return apiRequest<Payment>("/api/payments/", { method: "POST", body });
}
