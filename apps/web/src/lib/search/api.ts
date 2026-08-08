import { apiRequest } from "@/lib/api/client";

export type SearchHit = {
  id: number;
  label: string;
  subtitle: string;
  href: string;
};

export type GlobalSearchResult = {
  q: string;
  customers: SearchHit[];
  invoices: SearchHit[];
  tasks: SearchHit[];
  payments: SearchHit[];
  promises: SearchHit[];
};

export function globalSearch(q: string) {
  return apiRequest<GlobalSearchResult>("/api/search/", {
    query: { q },
  });
}
