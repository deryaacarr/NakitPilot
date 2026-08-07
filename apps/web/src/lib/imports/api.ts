import { apiRequest } from "@/lib/api/client";
import { env } from "@/lib/env";
import { getAccessToken } from "@/lib/auth/storage";
import { getOrganizationId } from "@/lib/api/organization";

import type {
  CommitResponse,
  DuplicatePolicy,
  ImportJob,
  PreviewResponse,
  UploadResponse,
} from "./types";

export function uploadInvoiceImport(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<UploadResponse>("/api/imports/invoices/upload/", {
    method: "POST",
    formData,
  });
}

export function saveImportMapping(
  jobId: number | string,
  columnMapping: Record<string, string | null>,
) {
  return apiRequest<{ job: ImportJob; unmapped_required: string[] }>(
    `/api/imports/${jobId}/mapping/`,
    {
      method: "PATCH",
      body: { column_mapping: columnMapping },
    },
  );
}

export function previewImport(
  jobId: number | string,
  options?: {
    columnMapping?: Record<string, string | null>;
    duplicatePolicy?: DuplicatePolicy;
  },
) {
  const body: Record<string, unknown> = {};
  if (options?.columnMapping) body.column_mapping = options.columnMapping;
  if (options?.duplicatePolicy) body.duplicate_policy = options.duplicatePolicy;
  return apiRequest<PreviewResponse>(`/api/imports/${jobId}/preview/`, {
    method: "POST",
    body,
  });
}

export function commitImport(jobId: number | string, duplicatePolicy?: DuplicatePolicy) {
  return apiRequest<CommitResponse>(`/api/imports/${jobId}/commit/`, {
    method: "POST",
    body: duplicatePolicy ? { duplicate_policy: duplicatePolicy } : {},
  });
}

export function getImportJob(jobId: number | string) {
  return apiRequest<ImportJob>(`/api/imports/${jobId}/`);
}

async function downloadAuthenticatedBlob(
  path: string,
  filename: string,
): Promise<{ ok: true } | { ok: false; message: string }> {
  const access = getAccessToken();
  const orgId = getOrganizationId();
  if (!access || !orgId) {
    return { ok: false, message: "Oturum veya organizasyon bulunamadı." };
  }
  try {
    const response = await fetch(`${env.apiUrl.replace(/\/$/, "")}${path}`, {
      headers: {
        Authorization: `Bearer ${access}`,
        "X-Organization-Id": orgId,
      },
    });
    if (!response.ok) {
      return { ok: false, message: "Dosya indirilemedi." };
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    return { ok: true };
  } catch {
    return { ok: false, message: "Dosya indirilemedi." };
  }
}

/** Authenticated template download (blob). */
export function downloadInvoiceTemplate() {
  return downloadAuthenticatedBlob(
    "/api/imports/invoices/template/",
    "nakitpilot_fatura_sablonu.xlsx",
  );
}

/** NP-067: download row errors as Excel. */
export function downloadImportErrors(jobId: number | string) {
  return downloadAuthenticatedBlob(
    `/api/imports/${jobId}/errors/export/`,
    `import_${jobId}_hatalar.xlsx`,
  );
}
