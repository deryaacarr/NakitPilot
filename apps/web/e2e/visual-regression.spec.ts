import { expect, test } from "@playwright/test";

/**
 * NP-503 — visual regression screenshots against /ui-gallery fixtures.
 * Update baselines: `npx playwright test e2e/visual-regression.spec.ts --update-snapshots`
 */
const SECTIONS = [
  "visual-button",
  "visual-input",
  "visual-table",
  "visual-dashboard",
  "visual-customer-detail",
  "visual-task-card",
  "visual-risk-badge",
] as const;

test.describe("NP-503 visual regression", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/ui-gallery");
    await expect(page.getByRole("heading", { name: "UI Gallery" })).toBeVisible();
  });

  for (const id of SECTIONS) {
    test(`${id} screenshot`, async ({ page }) => {
      const section = page.getByTestId(id);
      await expect(section).toBeVisible();
      await expect(section).toHaveScreenshot(`${id}.png`, {
        animations: "disabled",
        maxDiffPixelRatio: 0.02,
      });
    });
  }

  test("visual-modal open screenshot", async ({ page }) => {
    await page.getByTestId("visual-modal").getByRole("button", { name: "Modal aç" }).click();
    const dialog = page.getByRole("dialog", { name: "Görev tamamla" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveScreenshot("visual-modal-open.png", {
      animations: "disabled",
      maxDiffPixelRatio: 0.02,
    });
  });
});
