export type ApiKeyScope =
  | "customers:read"
  | "customers:write"
  | "invoices:read"
  | "invoices:write"
  | "payments:read"
  | "payments:write"
  | "risk:read"
  | "forecast:read"
  | string;

export type ApiKey = {
  id: number;
  name: string;
  display_prefix: string;
  prefix: string;
  scopes: ApiKeyScope[];
  is_active: boolean;
  last_used_at: string | null;
  revoked_at: string | null;
  created_by: number | null;
  created_by_email: string;
  created_at: string;
  updated_at: string;
};

export type ApiKeyCreated = ApiKey & {
  key: string;
};

export type ScopeOption = {
  value: string;
  label: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
