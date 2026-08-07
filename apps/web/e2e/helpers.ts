import { expect, type APIRequestContext, type BrowserContext, type Page } from "@playwright/test";

export const E2E_EMAIL = process.env.E2E_EMAIL ?? "demo@nakitpilot.local";
export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "DemoPass123!";
export const API_URL = (process.env.E2E_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const AUTH_COOKIE = "nakitpilot_access";

export async function apiLogin(request: APIRequestContext) {
  const res = await request.post(`${API_URL}/api/auth/login`, {
    data: { email: E2E_EMAIL, password: E2E_PASSWORD },
  });
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { access: string; refresh: string };
  const orgs = await request.get(`${API_URL}/api/memberships/me/`, {
    headers: { Authorization: `Bearer ${body.access}` },
  });
  expect(orgs.ok()).toBeTruthy();
  const memberships = (await orgs.json()) as Array<{ organization: number }>;
  const orgId = memberships[0]?.organization;
  expect(orgId).toBeTruthy();
  return { access: body.access, refresh: body.refresh, orgId: String(orgId) };
}

export async function seedSession(
  context: BrowserContext,
  page: Page,
  tokens: { access: string; refresh: string; orgId: string },
) {
  await context.addCookies([
    {
      name: AUTH_COOKIE,
      value: tokens.access,
      url: "http://localhost:3000/",
      httpOnly: false,
      sameSite: "Lax",
    },
  ]);
  // Apply storage on the current document (and keep cookie in sync with app format).
  await page.goto("http://localhost:3000/login");
  await page.evaluate(
    ({ access, refresh, orgId, cookieName }) => {
      window.localStorage.setItem("nakitpilot.access", access);
      window.localStorage.setItem("nakitpilot.refresh", refresh);
      window.localStorage.setItem("nakitpilot.remember", "1");
      window.localStorage.setItem("nakitpilot.organization_id", orgId);
      document.cookie = `${cookieName}=${encodeURIComponent(access)}; Path=/; Max-Age=${60 * 60 * 24 * 7}; SameSite=Lax`;
    },
    { ...tokens, cookieName: AUTH_COOKIE },
  );
}

export async function loginUi(page: Page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-form")).toHaveAttribute("data-hydrated", "true");
  await page.getByLabel("E-posta").fill(E2E_EMAIL);
  await page.getByLabel("Şifre").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Giriş yap" }).click();
  await expect(page).toHaveURL((url) => url.pathname === "/dashboard", { timeout: 30_000 });
  await expect
    .poll(async () => page.evaluate(() => window.localStorage.getItem("nakitpilot.access")))
    .not.toBeNull();
}

export function authHeaders(access: string, orgId: string) {
  return {
    Authorization: `Bearer ${access}`,
    "X-Organization-Id": orgId,
    "Content-Type": "application/json",
  };
}
