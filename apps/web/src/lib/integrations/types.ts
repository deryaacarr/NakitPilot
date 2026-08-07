export type IntegrationProvider = {
  provider: string;
  display_name: string;
};

export type SyncFrequency = "manual" | "hourly" | "daily";

export type ConnectionStatus = "draft" | "connected" | "error" | "disabled";

export type IntegrationConnection = {
  id: number;
  organization: number;
  provider: string;
  status: ConnectionStatus;
  external_company_id: string;
  external_company_name: string;
  settings_json: Record<string, unknown>;
  last_sync_at: string | null;
  last_successful_sync_at: string | null;
  next_sync_at: string | null;
  sync_frequency: SyncFrequency;
  last_error: string;
  has_credentials: boolean;
  key_hint: string;
  created_at: string;
  updated_at: string;
};

export type CredentialStatus = {
  has_credentials: boolean;
  key_hint: string;
  rotated_at: string | null;
};

export type CompanyOption = {
  external_id: string;
  name: string;
  tax_number: string;
};

export type SyncJob = {
  id: number;
  job_type: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  stats_json: Record<string, unknown>;
  error_message: string;
  created_at: string;
};

export type SyncConflictResolution =
  | "use_source"
  | "keep_local"
  | "merge"
  | "skip_field_forever";

export type SyncConflict = {
  id: number;
  connection: number;
  job: number | null;
  entity_type: string;
  conflict_type: string;
  status: "open" | "resolved" | string;
  external_id: string;
  internal_model: string;
  internal_id: string;
  message: string;
  source_payload: Record<string, unknown>;
  local_snapshot: Record<string, unknown>;
  resolution: string;
  resolution_detail: Record<string, unknown>;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
};

export type IntegrationMonitoring = {
  connection_id: number;
  status: string;
  last_sync_at: string | null;
  last_successful_sync_at: string | null;
  last_error: string;
  open_conflicts: number;
  metrics: {
    fetched: number;
    created: number;
    updated: number;
    skipped: number;
    failed: number;
    api_duration_ms: number | null;
    rate_limit: {
      limited: boolean;
      remaining: number | null;
      reset_at: string | null;
      message: string;
    };
    last_sync_duration_ms: number | null;
  };
  breakdown: Record<string, Record<string, unknown>>;
  entity_states: Array<{
    entity_type: string;
    last_cursor: string;
    last_remote_update_at: string | null;
    last_sync_at: string | null;
    last_successful_sync_at: string | null;
    checksum_count: number;
  }>;
  latest_job: {
    id: number;
    job_type: string;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    error_message: string;
  } | null;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
