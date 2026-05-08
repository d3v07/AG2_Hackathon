import { test, expect, Page } from "@playwright/test";

/**
 * Visual regression: golden screenshots per dashboard screen
 * at desktop (1440x900) and mobile (375x812).
 *
 * Scope: chromium only. The other projects (firefox) skip these tests
 * because cross-engine pixel diffs are noise, not signal.
 *
 * Production screen list (7). Sprint 16/17 screens (Forensic, Submit Run,
 * Workflows) are tracked as TODO and will be added once their PRs merge to
 * production.
 */

type ScreenSpec = {
  id: string;
  label: string;
  heading: RegExp;
};

const SCREENS: ScreenSpec[] = [
  { id: "overview", label: "Overview", heading: /Run Summary|Agent Pipeline/ },
  { id: "topology", label: "Workflow DAG", heading: /Workflow DAG/ },
  { id: "trace", label: "Agent Trace", heading: /Agent Trace/ },
  { id: "violations", label: "Violations", heading: /Contract Violations/ },
  { id: "repair", label: "Repair Patch", heading: /Repair Patch/ },
  { id: "regression", label: "Regression", heading: /Regression Test/ },
  { id: "report", label: "Final Report", heading: /Final Report/ },
];

// Sprint 16/17 follow-ups — uncomment after their PRs merge to production.
// const TODO_SCREENS: ScreenSpec[] = [
//   { id: "forensic", label: "Forensic", heading: /Forensic|Span Inspector/ },
//   { id: "submit", label: "Submit Run", heading: /Submit Run/ },
//   { id: "workflows", label: "Workflows", heading: /Workflows/ },
// ];

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 375, height: 812 };

const tabLocator = (page: Page, label: string) =>
  page.locator("nav.tabs .tab", { hasText: label });

const dynamicMasks = (page: Page) => [
  // The UTC clock under the status cluster is decorative and changes between
  // runs in live mode; mask to keep snapshots stable.
  page.locator(".status-line.muted"),
];

const navigateAndStabilize = async (page: Page, screen: ScreenSpec) => {
  await page.goto("/");
  await expect(page.locator(".topbar")).toBeVisible();
  await tabLocator(page, screen.label).dispatchEvent("click");
  await expect(page.locator("nav.tabs .tab.active")).toContainText(screen.label);
  await expect(page.getByRole("heading", { name: screen.heading }).first()).toBeVisible();
  await page.waitForLoadState("networkidle");
};

test.describe("visual regression: dashboard screens", () => {
  // Snapshots are scoped to chromium to avoid cross-engine pixel noise.
  test.beforeEach(({}, testInfo) => {
    test.skip(
      testInfo.project.name !== "chromium",
      "Visual snapshots run on chromium only.",
    );
  });

  test.describe("desktop 1440x900", () => {
    test.use({ viewport: DESKTOP });

    for (const screen of SCREENS) {
      test(`${screen.id} desktop`, async ({ page }) => {
        await navigateAndStabilize(page, screen);
        await expect(page).toHaveScreenshot(`${screen.id}-desktop.png`, {
          fullPage: true,
          animations: "disabled",
          mask: dynamicMasks(page),
        });
      });
    }
  });

  test.describe("mobile 375x812", () => {
    test.use({ viewport: MOBILE });

    for (const screen of SCREENS) {
      test(`${screen.id} mobile`, async ({ page }) => {
        await navigateAndStabilize(page, screen);
        await expect(page).toHaveScreenshot(`${screen.id}-mobile.png`, {
          fullPage: true,
          animations: "disabled",
          mask: dynamicMasks(page),
        });
      });
    }
  });
});
