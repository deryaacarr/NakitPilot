export type CallOutcome =
  | "REACHED"
  | "NOT_REACHED"
  | "PAYMENT_MADE"
  | "PROMISE_GIVEN"
  | "DISPUTED"
  | "WRONG_PERSON"
  | "CALLBACK";

export const OUTCOME_LABELS: Record<CallOutcome, string> = {
  REACHED: "Ulaşıldı",
  NOT_REACHED: "Ulaşılamadı",
  PAYMENT_MADE: "Ödeme yapıldı",
  PROMISE_GIVEN: "Ödeme sözü verdi",
  DISPUTED: "İtiraz etti",
  WRONG_PERSON: "Yanlış kişi",
  CALLBACK: "Tekrar aranacak",
};

export const TASK_TYPE_LABELS: Record<string, string> = {
  CALL: "Arama",
  EMAIL: "E-posta",
  WHATSAPP: "WhatsApp",
  FOLLOW_UP: "Takip",
  MEETING: "Toplantı",
  OTHER: "Diğer",
};

export type CollectionTask = {
  id: number;
  customer: number;
  customer_name: string;
  customer_risk_status: string;
  customer_phone?: string | null;
  invoice: number | null;
  invoice_number?: string | null;
  task_type: string;
  status: string;
  priority: string;
  priority_score: number;
  title: string;
  description: string;
  due_date: string;
  assigned_to: number | null;
  assigned_to_email?: string | null;
  assigned_to_name?: string | null;
  overdue_balance: string;
  overdue_days: number | null;
  last_contact_at: string | null;
  payment_promise: {
    id: number;
    promised_date: string;
    amount: string;
    status: string;
  } | null;
  outcome?: string;
  outcome_notes?: string;
};

export type TodayBoard = {
  overdue: CollectionTask[];
  today: CollectionTask[];
  upcoming: CollectionTask[];
  completed: CollectionTask[];
};

export type TimelineEvent = {
  id: string;
  kind: string;
  label: string;
  summary: string;
  notes: string;
  occurred_at: string;
  actor: string | null;
  metadata: Record<string, unknown>;
};

export type CompleteTaskPayload = {
  outcome: CallOutcome;
  outcome_notes: string;
  create_follow_up?: boolean;
  promise_given?: boolean;
  callback_date?: string | null;
  promise_amount?: string | null;
  promise_date?: string | null;
};
