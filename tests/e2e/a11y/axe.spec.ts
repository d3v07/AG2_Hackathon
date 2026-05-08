import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";
import { join } from "node:path";

type Allowlist = { ignored_rules: string[] };

const ALLOWLIST_PATH = join(__dirname, "axe-allowlist.json");
const ALLOWLIST: Allowlist = JSON.parse(readFileSync(ALLOWLIST_PATH, "utf8"));

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag22a", "wcag22aa"];

const SCREENS: { id: string; tab: string }[] = [
  { id: "overview", tab: "Overview" },
  { id: "trace", tab: "Agent Trace" },
  { id: "forensic", tab: "Forensic" },
  { id: "violations", tab: "Violations" },
  { id: "repair", tab: "Repair Patch" },
  { id: "regression", tab: "Regression" },
  { id: "report", tab: "Final Report" },
  { id: "submit", tab: "Submit Run" },
  { id: "workflows", tab: "Workflows" },
];

function formatViolations(violations: Awaited<ReturnType<AxeBuilder["analyze"]>>["violations"]): string {
  return violations
    .map((v) => {
      const nodes = v.nodes.map((n) => `      - ${n.target.join(", ")}\n        ${n.failureSummary ?? ""}`).join("\n");
      return `  [${v.impact ?? "n/a"}] ${v.id}: ${v.help}\n    ${v.helpUrl}\n${nodes}`;
    })
    .join("\n\n");
}

test.describe("axe-core a11y scan (WCAG 2.2 AA)", () => {
  for (const screen of SCREENS) {
    test(`screen: ${screen.tab}`, async ({ page }) => {
      await page.goto("/");
      await page.getByRole("button", { name: screen.tab }).click();
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
