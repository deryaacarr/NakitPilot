export type MessageChannel = "EMAIL" | "WHATSAPP" | "SMS";

export type MessageTemplate = {
  id: number;
  organization: number;
  name: string;
  channel: MessageChannel;
  subject: string;
  body: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

export type MessagePreview = {
  template_id: number;
  channel: MessageChannel;
  subject: string;
  body: string;
  variables: Record<string, string>;
};

export type MessageCopyResult = {
  copied: boolean;
  auto_sent: boolean;
  subject: string;
  body: string;
  activity_id: number | null;
  message: string;
};

/** NP-233 tone assistant */
export type MessageToneValue =
  | "NAZIK"
  | "PROFESYONEL"
  | "NET"
  | "SON_HATIRLATMA"
  | "YONETICI";

export type MessageToneOption = {
  value: MessageToneValue;
  label: string;
};

export type GeneratedMessage = {
  tone: MessageToneValue;
  tone_label: string;
  subject: string;
  body: string;
  variables: Record<string, string>;
  source_fields: {
    amount: string;
    invoice_number: string;
    due_date: string;
    overdue_days: string;
  };
};

export const CHANNEL_LABELS: Record<MessageChannel, string> = {
  EMAIL: "E-posta",
  WHATSAPP: "WhatsApp",
  SMS: "SMS",
};

export const DEFAULT_TONES: MessageToneOption[] = [
  { value: "NAZIK", label: "Nazik" },
  { value: "PROFESYONEL", label: "Profesyonel" },
  { value: "NET", label: "Net" },
  { value: "SON_HATIRLATMA", label: "Son hatırlatma" },
  { value: "YONETICI", label: "Yönetici dili" },
];

export const TEMPLATE_VARIABLES = [
  "customer_name",
  "invoice_number",
  "invoice_amount",
  "remaining_amount",
  "due_date",
  "overdue_days",
  "company_name",
  "payment_link",
] as const;

/** NP-240 outbound email */
export type OutboundEmailStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "QUEUED"
  | "SENDING"
  | "SENT"
  | "DELIVERED"
  | "OPENED"
  | "CLICKED"
  | "BOUNCED"
  | "FAILED"
  | "CANCELLED";

export type OutboundEmail = {
  id: number;
  public_id: string;
  customer_id: number;
  invoice_id: number | null;
  template_id: number | null;
  to_email: string;
  subject: string;
  body_text: string;
  status: OutboundEmailStatus;
  provider: string;
  sent_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
  bounced_at: string | null;
  open_count: number;
  click_count: number;
  bounce_type: string;
  error_message: string;
  created_at: string;
};

export type OutboundEmailPreview = {
  id: number;
  to_email: string;
  subject: string;
  body_text: string;
  body_html: string;
  status: OutboundEmailStatus;
  requires_approval: boolean;
  tracking_enabled: boolean;
};

export type EmailProviderConfig = {
  configured: boolean;
  id?: number;
  provider?: string;
  from_email?: string;
  from_name?: string;
  smtp_host?: string;
  smtp_port?: number;
  smtp_use_tls?: boolean;
  key_hint?: string;
  has_credentials?: boolean;
};

export const EMAIL_STATUS_LABELS: Record<OutboundEmailStatus, string> = {
  DRAFT: "Taslak",
  PENDING_APPROVAL: "Onay bekliyor",
  APPROVED: "Onaylandı",
  QUEUED: "Kuyrukta",
  SENDING: "Gönderiliyor",
  SENT: "Gönderildi",
  DELIVERED: "Teslim",
  OPENED: "Açıldı",
  CLICKED: "Tıklandı",
  BOUNCED: "Bounce",
  FAILED: "Başarısız",
  CANCELLED: "İptal",
};
