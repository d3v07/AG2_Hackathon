import { test, expect } from "@playwright/test";

// Failing-run navigation path: Violations -> click row -> Repair screen
// renders the selected patch (filtered to that patch only).

test.describe("violation -> repair navigation path", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/?fixture=1");
  });

  test("clicking a violation row navigates to Repair with that patch selected", async ({ page }) => {
    await page.locator("nav.tabs .tab", { hasText: "Violations" }).dispatchEvent("click");
    await expect(page.locator("nav.tabs .tab.active")).toContainText("Violations");
    await expect(page.getByRole("heading", { name: /Contract Violations/ })).toBeVisible();

    const dataRows = page.locator(".viol-row").filter({ hasNotText: /^Severity/ });
    const firstRow = dataRows.first();
    const patchCell = firstRow.locator(".text-gold").first();
    const patchId = (await patchCell.innerText()).trim();
    expect(patchId).toMatch(/^P-\d+/);

    await firstRow.click();
    await expect(page.locator("nav.tabs .tab.active")).toContainText("Repair Patch");
    await expect(page.getByRole("heading", { name: /Repair Patch/ })).toBeVisible();

    const patchBlocks = page.locator(".patch-block");
    await expect(patchBlocks).toHaveCount(1);
    await expect(patchBlocks.first().locator(".id").first()).toContainText(patchId);
    await expect(page.locator(".btn", { hasText: patchId })).toBeVisible();
  });

  test("Repair screen filter buttons switch the visible patch", async ({ page }) => {
    await page.locator("nav.tabs .tab", { hasText: "Violations" }).dispatchEvent("click");
    const dataRows = page.locator(".viol-row").filter({ hasNotText: /^Severity/ });
    await dataRows.first().click();
    await expect(page.locator("nav.tabs .tab.active")).toContainText("Repair Patch");

    await page.locator(".btn", { hasText: "ALL" }).click();
    const blockCount = await page.locator(".patch-block").count();
    expect(blockCount).toBeGreaterThan(1);
  });
});
