import { test, expect } from "@playwright/test";

// Forensic-style assertions against the production Trace surface.
// The dedicated Forensic screen with span tree + waterfall + inspector ships
// on the sprint-17 forensic-scaffold branch; on production the equivalent
// surface is the Agent Trace screen (TraceMiniRail waterfall + event rows
// driving a focused-step inspector).

test.describe("forensic / agent-trace UI", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.locator("nav.tabs .tab", { hasText: "Agent Trace" }).dispatchEvent("click");
    await expect(page.locator("nav.tabs .tab.active")).toContainText("Agent Trace");
  });

  test("renders the trace rail (waterfall), event tree, and inspector layout", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /Agent Trace/ })).toBeVisible();
    await expect(page.locator(".minirail")).toBeVisible();
    await expect(page.locator(".trace-layout")).toBeVisible();
    const rows = page.locator(".trace-row");
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);
    const railSteps = page.locator(".minirail .step");
    const stepCount = await railSteps.count();
    expect(stepCount).toBeGreaterThan(0);
  });

  test("clicking a tree row updates the inspector (focused step)", async ({ page }) => {
    const rows = page.locator(".trace-row");
    const target = rows.nth(2);
    await target.click();
    await expect(target).toHaveClass(/focused/);
    const focusedCount = await page.locator(".trace-row.focused").count();
    expect(focusedCount).toBe(1);
  });

  test("clicking a waterfall (rail) step updates the inspector", async ({ page }) => {
    const railSteps = page.locator(".minirail .step");
    await railSteps.nth(1).dispatchEvent("click");
    await expect(page.locator(".minirail .step.active")).toHaveCount(1);
    await expect(page.locator(".trace-row.focused")).toHaveCount(1);
  });

  test("selecting different events reassigns focus", async ({ page }) => {
    const rows = page.locator(".trace-row");
    await rows.nth(0).click();
    await expect(rows.nth(0)).toHaveClass(/focused/);
    await rows.nth(3).click();
    await expect(rows.nth(3)).toHaveClass(/focused/);
    await expect(rows.nth(0)).not.toHaveClass(/focused/);
  });
});
