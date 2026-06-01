import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.describe("fixture report export", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/?fixture=1");
    await page.locator("nav.tabs .tab", { hasText: "Final Report" }).dispatchEvent("click");
    await expect(page.getByRole("heading", { name: /Final Report/ })).toBeVisible();
  });

  test("downloads a complete report JSON payload", async ({ page }) => {
    const downloadPromise = page.waitForEvent("download");

    await page.getByRole("button", { name: "EXPORT JSON" }).click();

    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("concord-report-RUN-041.json");

    const path = await download.path();
    expect(path).toBeTruthy();
    const payload = JSON.parse(await readFile(path!, "utf8"));

    expect(payload.run.id).toBe("RUN-041");
    expect(payload.verdicts.violation_count).toBe(4);
    expect(payload.evidence.violations).toHaveLength(4);
    expect(payload.patches).toHaveLength(4);
    expect(payload.regression.test.assertions).toHaveLength(4);
    expect(payload.regression.validation_state).toBe("passed");
    expect(payload.cost).toEqual(
      expect.objectContaining({
        daytona_seconds: expect.any(Number),
        daytona_cost_usd: expect.any(Number),
      }),
    );
  });
});
