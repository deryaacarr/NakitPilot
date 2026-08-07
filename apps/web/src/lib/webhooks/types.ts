export type WebhookAttempt = {
  id: number;
  attempt_number: number;
  request_url: string;
  response_status: number | null;
  response_body: string;
  error_message: string;
  duration_ms: number | null;
  success: boolean;
  created_at: string;
};

export type WebhookDelivery = {
  id: number;
  public_id: string;
  endpoint: number;
  endpoint_name: string;
  endpoint_url: string;
  event_type: string;
  event_id: string;
  payload: Record<string, unknown>;
  status: string;
  attempt_count: number;
  max_attempts: number;
  next_attempt_at: string | null;
  last_error: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  attempts: WebhookAttempt[];
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
