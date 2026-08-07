import { apiRequest } from "@/lib/api/client";

import type {
  EmailProviderConfig,
  GeneratedMessage,
  MessageCopyResult,
  MessagePreview,
  MessageTemplate,
  MessageToneOption,
  MessageToneValue,
  OutboundEmail,
  OutboundEmailPreview,
} from "./types";

export function listMessageTemplates(channel?: string) {
  return apiRequest<MessageTemplate[]>("/api/message-templates/", {
    query: channel ? { channel } : undefined,
  });
}

export function listMessageTones() {
  return apiRequest<{ tones: MessageToneOption[] }>("/api/message-templates/tones/");
}

export function generateMessage(body: {
  customer_id: number;
  tone: MessageToneValue;
  invoice_id?: number | null;
  payment_link?: string;
}) {
  return apiRequest<GeneratedMessage>("/api/message-templates/generate/", {
    method: "POST",
    body,
  });
}

export function getMessageTemplate(id: number | string) {
  return apiRequest<MessageTemplate>(`/api/message-templates/${id}/`);
}

export function createMessageTemplate(
  body: Pick<MessageTemplate, "name" | "channel" | "subject" | "body" | "is_default">,
) {
  return apiRequest<MessageTemplate>("/api/message-templates/", { method: "POST", body });
}

export function updateMessageTemplate(
  id: number | string,
  body: Partial<Pick<MessageTemplate, "name" | "channel" | "subject" | "body" | "is_default">>,
) {
  return apiRequest<MessageTemplate>(`/api/message-templates/${id}/`, {
    method: "PATCH",
    body,
  });
}

export function previewMessageTemplate(
  id: number | string,
  body: { customer_id: number; invoice_id?: number | null; payment_link?: string },
) {
  return apiRequest<MessagePreview>(`/api/message-templates/${id}/preview/`, {
    method: "POST",
    body,
  });
}

export function copyMessageTemplate(
  id: number | string,
  body: {
    customer_id: number;
    invoice_id?: number | null;
    create_activity?: boolean;
    payment_link?: string;
    body?: string;
    subject?: string;
  },
) {
  return apiRequest<MessageCopyResult>(`/api/message-templates/${id}/copy/`, {
    method: "POST",
    body,
  });
}

export function listOutboundEmails(query?: { customer_id?: number; status?: string }) {
  return apiRequest<{ results: OutboundEmail[] }>("/api/message-templates/emails/", {
    query,
  });
}

export function createOutboundEmail(body: {
  customer_id: number;
  template_id?: number | null;
  invoice_id?: number | null;
  to_email?: string;
  subject?: string;
  body?: string;
  require_approval?: boolean;
}) {
  return apiRequest<OutboundEmail>("/api/message-templates/emails/", {
    method: "POST",
    body,
  });
}

export function previewOutboundEmail(id: number) {
  return apiRequest<OutboundEmailPreview>(`/api/message-templates/emails/${id}/preview/`, {
    method: "POST",
    body: {},
  });
}

export function approveOutboundEmail(
  id: number,
  body: { confirmed: boolean; queue_send?: boolean },
) {
  return apiRequest<OutboundEmail>(`/api/message-templates/emails/${id}/approve/`, {
    method: "POST",
    body,
  });
}

export function fetchEmailProviderConfig() {
  return apiRequest<EmailProviderConfig>("/api/message-templates/email-provider/");
}

export function saveEmailProviderConfig(body: {
  provider?: string;
  from_email: string;
  from_name?: string;
  smtp_host?: string;
  smtp_port?: number;
  smtp_use_tls?: boolean;
  username?: string;
  password?: string;
  api_key?: string;
}) {
  return apiRequest<EmailProviderConfig>("/api/message-templates/email-provider/", {
    method: "PUT",
    body,
  });
}
