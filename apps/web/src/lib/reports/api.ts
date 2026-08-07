import { apiRequest } from "@/lib/api/client";
import { getAccessToken } from "@/lib/auth/storage";
import { getOrganizationId } from "@/lib/api/organization";
import { env } from "@/lib/env";

export type ReportType = "OVERDUE_RECEIVABLES" | "COLLECTION_ACTIVITY" | "CUSTOMER_RISK";

export type ExportJob = {
  id: number;
  report_type: ReportType;
  report_type_label: string;
  status: "PREPARING" | "READY" | "FAILED" | "EXPIRED";
  status_label: string;
  filters: Record<string, unknown>;
  original_filename: string;
  file_size: number;
  row_count: number;
  error_message: string;
  expires_at: string | null;
  created_at: string;
  completed_at: string | null;
};

export type ReportPreview<T> = {
  count: number;
  results: T[];
};

export type OverdueRow = {
  customer_name: string;
  invoice_number: string;
  open_balance: string;
  due_date: string;
  overdue_days: number;
  risk_status: string;
  risk_score: number;
  last_contact_at: string;
  payment_promise: string;
};

export type ActivityRow = {
  user_id: number;
  user_name: string;
  user_email: string;
  tasks_completed: number;
  contacts_made: number;
  promises_taken: number;
  promises_kept: number;
  promises_broken: number;
  collected_amount: string;
};

export type RiskRow = {
  customer_name: string;
  customer_code: string;
  risk_score: number;
  risk_status: string;
  risk_reasons: string;
  overdue_balance: string;
  avg_delay_days: number | null;
  broken_promise_count: number;
  last_payment_date: string;
};

const SLUG: Record<ReportType, string> = {
  OVERDUE_RECEIVABLES: "overdue-receivables",
  COLLECTION_ACTIVITY: "collection-activity",
  CUSTOMER_RISK: "customer-risk",
};

export function fetchReportPreview<T>(
  reportType: ReportType,
  query?: Record<string, string | number | boolean | null | undefined>,
) {
  return apiRequest<ReportPreview<T>>(`/api/reports/${SLUG[reportType]}/`, { query });
}

export function createReportExport(reportType: ReportType, filters: Record<string, unknown> = {}) {
  return apiRequest<ExportJob>("/api/reports/exports/", {
    method: "POST",
    body: { report_type: reportType, filters },
  });
}

export function fetchExportJob(id: number) {
  return apiRequest<ExportJob>(`/api/reports/exports/${id}/`);
}

export async function downloadExportJob(id: number): Promise<{ ok: true } | { ok: false; detail: string }> {
  const access = getAccessToken();
  const org = getOrganizationId();
  if (!access) return { ok: false, detail: "Oturum bulunamadı." };

  const base = env.apiUrl.replace(/\/$/, "");
  const response = await fetch(`${base}/api/reports/exports/${id}/download/`, {
    headers: {
      Authorization: `Bearer ${access}`,
      ...(org ? { "X-Organization-Id": String(org) } : {}),
    },
  });

  if (!response.ok) {
    let detail = "İndirme başarısız.";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    return { ok: false, detail };
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match?.[1] || `rapor-${id}.xlsx`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return { ok: true };
}
