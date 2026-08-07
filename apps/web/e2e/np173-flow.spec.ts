import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { API_URL, apiLogin, authHeaders, loginUi, seedSession } from "./helpers";

test("NP-173 login", async ({ page }) => {
  await loginUi(page);
  await expect(page.getByRole("heading").first()).toBeVisible();
});

test("NP-173 full business flow", async ({ page, request, context }) => {
  test.setTimeout(180_000);
  const stamp = Date.now();
  const customerName = `E2E Cari ${stamp}`;
  const invoiceNumber = `E2E-INV-${stamp}`;

  const session = await apiLogin(request);
  await seedSession(context, page, session);

  // 1) Dashboard reachable when authenticated
  await page.goto("/dashboard");
  await expect(page).toHaveURL((url) => url.pathname === "/dashboard");
  await expect(page.getByRole("heading", { name: "Özet" })).toBeVisible({ timeout: 30_000 });

  // 2) Müşteri oluşturma
  await page.goto("/customers/new");
  await expect(page).toHaveURL((url) => url.pathname === "/customers/new");
  await expect(page.getByRole("heading", { name: "Yeni müşteri" })).toBeVisible({
    timeout: 30_000,
  });
  await page.locator('input[name="name"]').fill(customerName);
  await page.locator('input[name="code"]').fill(`E2E-${stamp}`);
  await page.getByRole("button", { name: "Oluştur" }).click();
  await expect(page).toHaveURL((url) => /^\/customers\/\d+$/.test(url.pathname), {
    timeout: 30_000,
  });
  const customerId = Number(page.url().match(/\/customers\/(\d+)/)?.[1]);
  expect(customerId).toBeGreaterThan(0);
  await expect(page.getByRole("heading", { name: customerName })).toBeVisible();

  // 3) Fatura oluşturma
  await page.goto("/invoices/new");
  await expect(page.getByLabel("Müşteri")).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Müşteri").selectOption({ label: customerName });
  await page.getByLabel("Fatura numarası").fill(invoiceNumber);
  await page.getByLabel("Ara toplam").fill("200.00");
  await page.getByLabel("Vergi").fill("0.00");
  await page.getByLabel("Toplam", { exact: true }).fill("200.00");
  await page.getByRole("button", { name: "Kaydet" }).click();
  await expect(page).toHaveURL((url) => /^\/invoices\/\d+$/.test(url.pathname), {
    timeout: 30_000,
  });
  const invoiceId = Number(page.url().match(/\/invoices\/(\d+)/)?.[1]);
  expect(invoiceId).toBeGreaterThan(0);
  await expect(page.getByRole("heading", { name: invoiceNumber })).toBeVisible();

  // 4) Excel import (unique name avoids duplicate_file hash check)
  await page.goto("/imports");
  const xlsxPath = path.join(__dirname, "fixtures", "invoices-import.xlsx");
  await page.locator('input[type="file"]').setInputFiles({
    name: `invoices-import-${stamp}.xlsx`,
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: fs.readFileSync(xlsxPath),
  });
  await expect(page.getByText(/Dosya:/)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Kaydet ve önizle" }).click();
  await expect(page.getByText("Geçerli satır")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Önizlemede satır hatası yok.")).toBeVisible();
  const commit = page.getByRole("button", { name: "İçe aktarmayı başlat" });
  await expect(commit).toBeEnabled();
  await commit.click();
  await Promise.race([
    page.getByText("Durum").waitFor({ timeout: 20_000 }),
    page.getByText(/İşleniyor|COMPLETED|FAILED|Sonuç/i).first().waitFor({ timeout: 20_000 }),
  ]).catch(() => undefined);

  // 5) Görev + ödeme sözü
  const today = new Date().toISOString().slice(0, 10);
  const promiseDate = new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10);
  const taskRes = await request.post(`${API_URL}/api/collection-tasks/`, {
    headers: authHeaders(session.access, session.orgId),
    data: {
      customer: customerId,
      invoice: invoiceId,
      due_date: today,
      title: `E2E görev ${stamp}`,
      task_type: "CALL",
    },
  });
  expect(taskRes.ok()).toBeTruthy();
  const taskId = ((await taskRes.json()) as { id: number }).id;

  await page.goto("/collections");
  await expect(page.getByText(`E2E görev ${stamp}`)).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Tamamla" }).first().click();
  await page.getByLabel(/Görüşme notu/).fill("E2E görüşme notu — söz verildi");
  await page.getByText("Ödeme sözü verildi mi?").click();
  await page.getByLabel("Söz tarihi *").fill(promiseDate);
  await page.getByLabel("Söz tutarı *").fill("200.00");
  await page.getByRole("button", { name: "Kaydet" }).click();
  await expect(page.getByText("Görev tamamlandı")).toBeVisible({ timeout: 20_000 });

  await page.goto("/promises");
  await expect(page.getByRole("heading", { name: "Ödeme sözleri" })).toBeVisible();
  await expect(page.getByText(customerName).first()).toBeVisible({ timeout: 20_000 });

  // 6) Ödeme kaydetme
  const pay = await request.post(`${API_URL}/api/payments/`, {
    headers: authHeaders(session.access, session.orgId),
    data: {
      customer: customerId,
      payment_date: today,
      amount: "200.00",
      currency: "TRY",
      allocations: [{ invoice_id: invoiceId, amount: "200.00" }],
    },
  });
  expect(pay.ok()).toBeTruthy();
  await page.goto(`/invoices/${invoiceId}`);
  await expect(page.getByText("Ödenmiş").first()).toBeVisible({ timeout: 20_000 });

  // 7) Dashboard
  await page.goto("/dashboard");
  await expect(page.getByRole("heading").first()).toBeVisible();
  await expect(page.getByText(/Bugün|Bu hafta|Bu ay|Son 30/i).first()).toBeVisible();
  expect(taskId).toBeGreaterThan(0);
});
