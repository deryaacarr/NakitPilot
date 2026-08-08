import { apiRequest } from "@/lib/api/client";

import type { LegalCase, LegalCaseDetail, LegalCriteria } from "./types";

export function listLegalCases() {
  return apiRequest<{ count: number; results: LegalCase[] }>("/api/legal/cases/");
}

export function getLegalCase(id: number) {
  return apiRequest<LegalCaseDetail>(`/api/legal/cases/${id}/`);
}

export function createLegalCase(body: {
  customer: number;
  title?: string;
  notes?: string;
  invoice_ids?: number[];
}) {
  return apiRequest<LegalCaseDetail>("/api/legal/cases/", { method: "POST", body });
}

export function fetchLegalCriteria(customerId: number) {
  return apiRequest<LegalCriteria>(`/api/legal/criteria/${customerId}/`);
}

export function approveLegalCase(id: number) {
  return apiRequest<LegalCaseDetail>(`/api/legal/cases/${id}/approve/`, { method: "POST", body: {} });
}

export function handoffLegalCase(id: number, lawyerId: number, note = "") {
  return apiRequest<LegalCaseDetail>(`/api/legal/cases/${id}/handoff/`, {
    method: "POST",
    body: { lawyer_id: lawyerId, note },
  });
}

export function updateLegalCaseStatus(id: number, status: string, note = "") {
  return apiRequest<LegalCaseDetail>(`/api/legal/cases/${id}/status/`, {
    method: "POST",
    body: { status, note },
  });
}

export function generateLegalPackage(id: number) {
  return apiRequest<{ package_path: string; download_url: string }>(
    `/api/legal/cases/${id}/package/`,
    { method: "POST", body: {} },
  );
}

export function addLegalActivity(id: number, summary: string, notes = "") {
  return apiRequest(`/api/legal/cases/${id}/activities/`, {
    method: "POST",
    body: { summary, notes },
  });
}
