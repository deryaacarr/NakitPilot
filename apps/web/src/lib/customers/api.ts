import { apiRequest } from "@/lib/api/client";

import type {
  Customer,
  CustomerContact,
  CustomerContactInput,
  CustomerInput,
  CustomerListParams,
  Paginated,
  RiskExplanation,
  RiskHistoryPoint,
} from "./types";

export function listCustomers(params: CustomerListParams = {}) {
  return apiRequest<Paginated<Customer>>("/api/customers/", { query: params });
}

export function getCustomer(id: number | string) {
  return apiRequest<Customer>(`/api/customers/${id}/`);
}

export function createCustomer(body: CustomerInput) {
  return apiRequest<Customer>("/api/customers/", { method: "POST", body });
}

export function updateCustomer(id: number | string, body: Partial<CustomerInput>) {
  return apiRequest<Customer>(`/api/customers/${id}/`, { method: "PATCH", body });
}

export function deactivateCustomer(id: number | string) {
  return apiRequest<Customer>(`/api/customers/${id}/`, { method: "DELETE" });
}

export function listContacts(customerId: number | string) {
  return apiRequest<CustomerContact[]>(`/api/customers/${customerId}/contacts/`);
}

export function createContact(customerId: number | string, body: CustomerContactInput) {
  return apiRequest<CustomerContact>(`/api/customers/${customerId}/contacts/`, {
    method: "POST",
    body,
  });
}

export function updateContact(
  customerId: number | string,
  contactId: number | string,
  body: Partial<CustomerContactInput>,
) {
  return apiRequest<CustomerContact>(`/api/customers/${customerId}/contacts/${contactId}/`, {
    method: "PATCH",
    body,
  });
}

export function deleteContact(customerId: number | string, contactId: number | string) {
  return apiRequest<null>(`/api/customers/${customerId}/contacts/${contactId}/`, {
    method: "DELETE",
  });
}

export type RiskHistoryRange = "30d" | "90d" | "12m";

export function fetchCustomerRiskHistory(
  customerId: number | string,
  range: RiskHistoryRange = "30d",
) {
  return apiRequest<{ range: RiskHistoryRange; points: RiskHistoryPoint[] }>(
    `/api/customers/${customerId}/risk-history/`,
    { query: { range } },
  );
}

export function fetchCustomerRiskExplanation(customerId: number | string) {
  return apiRequest<RiskExplanation>(`/api/customers/${customerId}/risk-explanation/`);
}
