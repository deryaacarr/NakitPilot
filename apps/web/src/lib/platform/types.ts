export type PlatformOverview = {
  as_of: string;
  privacy: { customer_data_included: boolean; note: string };
  totals: {
    organizations: number;
    active_users: number;
    active_memberships: number;
  };
  organizations: Array<{
    id: number;
    name: string;
    slug: string;
    user_count: number;
    created_at: string | null;
  }>;
  plans: Array<{ id: number; code: string; name: string; sub_count: number }>;
  subscriptions: Array<{
    id: number;
    status: string;
    organization_id: number;
    organization_name: string;
    plan_code: string;
  }>;
  integrations: { by_status: Array<{ status: string; count: number }> };
  last_errors: Array<{
    source: string;
    id: number;
    organization_id: number | null;
    message: string;
    at: string | null;
  }>;
  support_tickets: Array<{
    id: number;
    subject: string;
    status: string;
    organization_id: number;
    organization_name: string;
  }>;
  ai_cost: { estimated_cost_total: string; events: number };
  storage: { file_storage_bytes: number; note?: string };
  customer_aggregates?: { customer_count: number; invoice_count: number };
};

export type FeatureFlag = {
  id: number;
  key: string;
  description: string;
  enabled: boolean;
  environments: string[];
  plan_codes: string[];
  organization_ids: number[];
  rollout_percentage: number;
};

export type MaintenanceWindow = {
  id: number;
  scope: string;
  mode: string;
  organization: number | null;
  module: string;
  message: string;
  is_active: boolean;
  starts_at: string;
  ends_at: string | null;
};

export type ImpersonationStartResult = {
  access: string;
  refresh: string;
  session_id: string;
  expires_at: string;
  organization_id: number;
  banner: string;
  reason: string;
  sensitive_writes_blocked: boolean;
  target_user: { id: number; email: string; name: string };
  staff_user: { id: number; email: string };
};

export type ImpersonationStatus = {
  active: boolean;
  session_id?: string;
  banner?: string;
  expires_at?: string;
  reason?: string;
  staff_email?: string;
  target_email?: string;
  sensitive_writes_blocked?: boolean;
};

export type SupportTicket = {
  id: number;
  organization: number;
  organization_name: string;
  subject: string;
  body: string;
  status: string;
};
