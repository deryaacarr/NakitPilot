export const LEGAL_STATUS_LABELS: Record<string, string> = {
  PREPARING: "Hazırlanıyor",
  HANDED_TO_LAWYER: "Avukata aktarıldı",
  NOTICE: "İhtar aşaması",
  MEDIATION: "Arabuluculuk",
  LAWSUIT: "Dava",
  ENFORCEMENT: "İcra",
  COLLECTED: "Tahsil edildi",
  CLOSED: "Kapatıldı",
};

export type LegalCase = {
  id: number;
  customer: number;
  customer_name: string;
  title: string;
  status: string;
  balance_at_open: string;
  manager_approved: boolean;
  assigned_lawyer: number | null;
  assigned_lawyer_email?: string | null;
  opened_at: string;
  updated_at: string;
};

export type LegalCaseDetail = LegalCase & {
  criteria_snapshot: Record<string, unknown>;
  notes: string;
  package_path?: string;
  package_generated_at?: string | null;
  case_invoices?: Array<{ id: number; invoice: number; invoice_number: string; amount_at_link: string }>;
  activities?: Array<{ id: number; summary: string; notes: string; occurred_at: string }>;
  documents?: Array<{ id: number; original_filename: string; created_at: string }>;
  status_history?: Array<{
    id: number;
    from_status: string;
    to_status: string;
    note: string;
    occurred_at: string;
  }>;
  disclaimer?: string;
};

export type LegalCriteria = {
  customer_id: number;
  customer_name: string;
  open_balance: string;
  overdue_days: number;
  broken_promises: number;
  operational_criteria_met: boolean;
  eligible_for_handoff: boolean;
  disclaimer: string;
  rules: Array<{
    code: string;
    label: string;
    met: boolean;
    value: string | number | boolean;
    threshold: string | number | boolean;
  }>;
};
