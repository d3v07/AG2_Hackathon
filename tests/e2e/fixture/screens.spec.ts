import { test, expect, Page, ConsoleMessage } from "@playwright/test";

type ScreenSpec = {
  id: string;
  num: string;
  label: string;
  heading: RegExp;
};

const SCREENS: ScreenSpec[] = [
  { id: "overview", num: "01", label: "Overview", heading: /Run Summary|Agent Pipeline/ },
  { id: "topology", num: "02", label: "Workflow DAG", heading: /Workflow DAG/ },
  { id: "trace", num: "03", label: "Agent Trace", heading: /Agent Trace/ },
  { id: "violations", num: "04", label: "Violations", heading: /Contract Violations/ },
  { id: "repair", num: "05", label: "Repair Patch", heading: /Repair Patch/ },
  { id: "regression", num: "06", label: "Regression", heading: /Regression Test/ },
  { id: "report", num: "07", label: "Final Report", heading: /Final Report/ },
];

const tabLocator = (page: Page, label: string) =>
  page.locator("nav.tabs .tab", { hasText: label });

const attachConsoleErrors = (page: Page): string[] => {
  const errors: string[] = [];
  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err: Error) => {
    errors.push(err.message);
  });
  return errors;
};

test.describe("fixture-mode dashboard screens", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/?fixture=1");
    await expect(page.locator(".topbar")).toBeVisible();
    await expect(page.locator("nav.tabs .tab")).toHaveCount(SCREENS.length);
  });

  test("default screen renders the Overview landmark", async ({ page }) => {
    const errors = attachConsoleErrors(page);
    await expect(page.locator("nav.tabs .tab.active")).toContainText(/Overview/);
    await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
    expect(errors, errors.join("\n")).toEqual([]);
  });

  for (const screen of SCREENS) {
    test(`screen ${screen.num} ${screen.label} renders without console errors`, async ({ page }) => {
      const errors = attachConsoleErrors(page);
      await tabLocator(page, screen.label).dispatchEvent("click");
      await expect(page.locator("nav.tabs .tab.active")).toContainText(screen.label);
      await expect(page.getByRole("heading", { name: screen.heading }).first()).toBeVisible();
      expect(errors, errors.join("\n")).toEqual([]);
    });
  }

  test("nav tabs are reachable via keyboard", async ({ page }) => {
    const tabs = page.locator("nav.tabs .tab");
    await tabs.nth(0).focus();
    await expect(tabs.nth(0)).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(tabs.nth(1)).toBeFocused();
  });
});
