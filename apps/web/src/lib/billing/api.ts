import { apiRequest } from "@/lib/api/client";

export type SubscriptionPlan = {
  id: number;
  code: string;
  name: string;
  description: string;
  price_monthly: string;
  price_yearly: string;
  sort_order: number;
  entitlements: Record<string, unknown>;
};

export type SubscriptionMe = {
  id: number;
  status: string;
  plan: { code: string; name: string; price_monthly: string; price_yearly?: string };
  seats: number;
  trial_ends_at: string | null;
  card_required: boolean;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  read_only: boolean;
  dunning_step: number;
  next_retry_at: string | null;
  grace_ends_at: string | null;
  scheduled_plan: { code: string; name: string } | null;
  scheduled_plan_at: string | null;
  payment_method: { brand: string; last4: string; provider: string };
  entitlements: Record<string, unknown>;
  usage: {
    period_start: string;
    period_end: string;
    metrics: Record<string, number>;
    limits: Record<string, number | null | undefined>;
    labels: Record<string, string>;
  };
};

export type BillingInvoice = {
  id: number;
  number: string;
  status: string;
  total: string;
  currency: string;
  period_start: string | null;
  period_end: string | null;
  paid_at: string | null;
  line_items: unknown[];
  pdf_available: boolean;
};

export type TrialProgress = {
  status: string;
  trial_ends_at: string | null;
  days_left: number | null;
  card_required: boolean;
  read_only: boolean;
  steps: Array<{ key: string; label: string; done: boolean; detail: string; count?: number }>;
  completed_steps: number;
  total_steps: number;
  progress_pct: number;
};

export type RevenueMetrics = {
  mrr: string;
  arr: string;
  active_subscriptions: number;
  trial_users: number;
  conversion_rate: number;
  churn: number;
  arpu: string;
  failed_payments: number;
  plan_distribution: Record<string, number>;
  as_of: string;
};

export function fetchPlans() {
  return apiRequest<{ results: SubscriptionPlan[] }>("/api/billing/plans/");
}

export function fetchSubscription() {
  return apiRequest<SubscriptionMe>("/api/billing/subscription/");
}

export function changePlan(plan_code: string) {
  return apiRequest<SubscriptionMe>("/api/billing/subscription/", {
    method: "POST",
    body: { plan_code },
  });
}

export function startCheckout(plan_code: string, payment_token = "") {
  return apiRequest<{
    checkout_id: string;
    invoice_id: number;
    amount: string;
    status: string;
    client_secret: string;
  }>("/api/billing/checkout/", {
    method: "POST",
    body: { plan_code, payment_token },
  });
}

export function confirmCheckout(checkout_id: string, plan_code: string) {
  return apiRequest<{ status: string; plan_code: string }>("/api/billing/webhooks/payments/", {
    method: "POST",
    body: {
      event: "payment.succeeded",
      checkout_id,
      plan_code,
    },
  });
}

export function scheduleDowngrade(plan_code: string) {
  return apiRequest<SubscriptionMe>("/api/billing/subscription/schedule-downgrade/", {
    method: "POST",
    body: { plan_code },
  });
}

export function updatePaymentMethod(brand: string, last4: string) {
  return apiRequest<SubscriptionMe>("/api/billing/subscription/payment-method/", {
    method: "POST",
    body: { brand, last4 },
  });
}

export function cancelSubscription(at_period_end = true) {
  return apiRequest<SubscriptionMe>("/api/billing/subscription/cancel/", {
    method: "POST",
    body: { at_period_end },
  });
}

export function fetchUsage() {
  return apiRequest<SubscriptionMe["usage"]>("/api/billing/usage/");
}

export function fetchTrial() {
  return apiRequest<TrialProgress>("/api/billing/trial/");
}

export function fetchBillingInvoices() {
  return apiRequest<{ results: BillingInvoice[] }>("/api/billing/invoices/");
}

export function fetchAdminRevenue() {
  return apiRequest<RevenueMetrics>("/api/billing/admin/revenue/");
}
