import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

type Allowlist = { ignored_rules: string[] };

const __dirname = dirname(fileURLToPath(import.meta.url));
const ALLOWLIST_PATH = join(__dirname, "axe-allowlist.json");
const ALLOWLIST: Allowlist = JSON.parse(readFileSync(ALLOWLIST_PATH, "utf8"));

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag22a", "wcag22aa"];

// Production index.html ships these 7 screens. Sprint 16/17 added Submit Run,
// Workflows, and Forensic to public/app.jsx (the dev module) but they aren't
// yet wired into the inline JSX in public/index.html. When the inline JSX
// migrates to load app.jsx as a module, append the missing tabs here.
const SCREENS: { id: string; tab: string }[] = [
  { id: "overview", tab: "Overview" },
  { id: "topology", tab: "Workflow DAG" },
  { id: "trace", tab: "Agent Trace" },
  { id: "violations", tab: "Violations" },
  { id: "repair", tab: "Repair Patch" },
  { id: "regression", tab: "Regression" },
  { id: "report", tab: "Final Report" },
];

function formatViolations(violations: Awaited<ReturnType<AxeBuilder["analyze"]>>["violations"]): string {
  return violations
    .map((v) => {
      const nodes = v.nodes.map((n) => `      - ${n.target.join(", ")}\n        ${n.failureSummary ?? ""}`).join("\n");
      return `  [${v.impact ?? "n/a"}] ${v.id}: ${v.help}\n    ${v.helpUrl}\n${nodes}`;
    })
    .join("\n\n");
}

// 1600x900 keeps the topbar status cluster from overlapping the rightmost
// tabs (Regression / Final Report) — same fix as #91 visual regression.
test.use({ viewport: { width: 1600, height: 900 } });

test.describe("axe-core a11y scan (WCAG 2.2 AA)", () => {
  for (const screen of SCREENS) {
    test(`screen: ${screen.tab}`, async ({ page }) => {
      await page.goto("/?fixture=1");
      const tab = page.getByRole("button", { name: screen.tab });
      // dispatchEvent fires React's onClick even if a higher-z-index
      // element would otherwise intercept pointer events
      await tab.dispatchEvent("click");
      await page.waitForLoadState("networkidle");

      const builder = new AxeBuilder({ page }).withTags(WCAG_TAGS);
      if (ALLOWLIST.ignored_rules.length > 0) {
        builder.disableRules(ALLOWLIST.ignored_rules);
      }
      const results = await builder.analyze();

      expect(
        results.violations,
        `WCAG 2.2 AA violations on ${screen.tab}:\n${formatViolations(results.violations)}`,
      ).toEqual([]);
    });
  }
});
