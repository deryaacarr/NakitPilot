import { expect, test, type Page } from "@playwright/test";

/**
 * NP-502 — viewport audit against documented breakpoints.
 */
const VIEWPORTS = [
  { name: "375", width: 375, height: 812 },
  { name: "430", width: 430, height: 932 },
  { name: "768", width: 768, height: 1024 },
  { name: "1024", width: 1024, height: 768 },
  { name: "1366", width: 1366, height: 768 },
  { name: "1440", width: 1440, height: 900 },
  { name: "1920", width: 1920, height: 1080 },
  { name: "2560", width: 2560, height: 1440 },
] as const;

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return {
      scrollWidth: doc.scrollWidth,
      clientWidth: doc.clientWidth,
    };
  });
  expect(
    overflow.scrollWidth,
    `Horizontal overflow: scrollWidth=${overflow.scrollWidth} clientWidth=${overflow.clientWidth}`,
  ).toBeLessThanOrEqual(overflow.clientWidth + 1);
}

test.describe("NP-502 responsive breakpoints", () => {
  for (const vp of VIEWPORTS) {
    test(`ui-gallery @ ${vp.name}px — no horizontal overflow`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/ui-gallery");
      await expect(page.getByRole("heading", { name: "UI Gallery" })).toBeVisible();
      await assertNoHorizontalOverflow(page);

      // Mobile: primary actions visible
      if (vp.width <= 430) {
        await expect(page.getByTestId("visual-button").getByRole("button").first()).toBeVisible();
        await expect(page.getByTestId("visual-task-card")).toBeVisible();
      }

      // Wide: content should use available width (not a tiny centered column)
      if (vp.width >= 1920) {
        const main = page.locator("main .max-w-5xl");
        const box = await main.boundingBox();
        expect(box).toBeTruthy();
        expect(box!.width).toBeGreaterThan(900);
      }

      // Ultrawide: prose measure stays readable
      if (vp.width >= 2560) {
        const prose = page.getByTestId("prose-measure");
        const box = await prose.boundingBox();
        expect(box).toBeTruthy();
        expect(box!.width).toBeLessThan(720);
      }
    });
  }

  test("1366px — dashboard shell content does not overflow (auth optional)", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/ui-gallery");
    await assertNoHorizontalOverflow(page);
    const table = page.getByTestId("visual-table");
    await expect(table).toBeVisible();
    const box = await table.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.x + box!.width).toBeLessThanOrEqual(1366 + 2);
  });
});
