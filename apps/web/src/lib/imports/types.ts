export type CanonicalField = {
  key: string;
  label: string;
  required: boolean;
};

export type DuplicatePolicy = "SKIP" | "UPDATE" | "CREATE";

export type ImportJobStatus =
  "PENDING" | "VALIDATING" | "READY" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED";

export type ImportJob = {
  id: number;
  organization: number;
  import_type: string;
  status: ImportJobStatus | string;
  duplicate_policy: DuplicatePolicy | string;
  original_filename: string;
  content_type: string;
  file_size: number;
  file_hash: string;
  headers: string[];
  column_mapping: Record<string, string | null>;
  preview_summary: ImportPreviewSummary | Record<string, never>;
  preview_errors: ImportPreviewError[];
  result_summary: ImportResultSummary | Record<string, never>;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  successful_rows: number;
  failed_rows: number;
  skipped_duplicates: number;
  celery_task_id: string;
  uploaded_by: number | null;
  uploaded_by_email?: string;
  error_message: string;
  created_at: string;
  updated_at: string;
};

export type ImportPreviewSummary = {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  new_customer_count: number;
  new_invoice_count: number;
  likely_duplicate_count: number;
  skipped_duplicate_count?: number;
  error_count: number;
  duplicate_policy?: string;
};

export type ImportResultSummary = {
  successful_rows: number;
  failed_rows: number;
  skipped_duplicates: number;
  total_rows: number;
  duplicate_policy?: string;
};

export type ImportPreviewError = {
  row_number: number;
  field_name: string;
  raw_value: string;
  error_message: string;
  kind?: string;
};

export type UploadResponse = {
  job: ImportJob;
  suggested_mapping: Record<string, string | null>;
  unmapped_required: string[];
  canonical_fields: CanonicalField[];
};

export type PreviewResponse = {
  job: ImportJob;
  summary: ImportPreviewSummary;
  errors: ImportPreviewError[];
  mapping: Record<string, string | null>;
};

export type CommitResponse = {
  job: ImportJob;
  task_id: string;
};
