const ORG_KEY = "nakitpilot.organization_id";

export function getOrganizationId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ORG_KEY);
}

export function setOrganizationId(id: string | number): void {
  window.localStorage.setItem(ORG_KEY, String(id));
}

export function clearOrganizationId(): void {
  window.localStorage.removeItem(ORG_KEY);
}
