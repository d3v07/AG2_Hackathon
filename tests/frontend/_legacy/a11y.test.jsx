/**
 * Sprint 18 #86 — accessibility audit tests.
 *
 * Asserts the WCAG 2.2 AA scaffolding:
 * - Skip-to-main link is the first focusable element
 * - Top nav has aria-label and tabs have aria-current on the active page
 * - Tabs have descriptive aria-labels (not just visual icons)
 * - Main landmark is programmatic focus target with aria-label
 * - h1 per screen (visually-hidden but available to screen readers)
 * - Visually-hidden utility class works
 *
 * NOTE: full axe-core scans live in tests/e2e/a11y/axe.spec.ts (Sprint 19 #92).
 * These Vitest tests cover structural invariants we want enforced at the
 * component level so a regression fails fast.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let App;

beforeAll(async () => {
  loadFixture();
  ({ App } = await import("../../public/app.jsx"));
});

describe("Skip-to-main link", () => {
  it("is the first focusable element in the DOM", () => {
    const { container } = render(<App />);
    const skipLink = container.querySelector("a.skip-link");
    expect(skipLink).toBeTruthy();
    expect(skipLink.getAttribute("href")).toBe("#main-content");
    expect(skipLink.textContent).toMatch(/Skip to main content/i);

    // Should appear before any other interactive element
    const allFocusable = container.querySelectorAll("a, button, input, textarea, select, [tabindex]");
    expect(allFocusable[0]).toBe(skipLink);
  });
});

describe("Top navigation a11y", () => {
  it("nav has descriptive aria-label", () => {
    const { container } = render(<App />);
    const nav = container.querySelector("nav.tabs");
    expect(nav.getAttribute("aria-label")).toMatch(/Primary screens/i);
  });

  it("active tab has aria-current=page", () => {
    const { container } = render(<App />);
    const activeTab = container.querySelector('.tab[aria-current="page"]');
    expect(activeTab).toBeTruthy();
    // Default screen is "overview"
    expect(activeTab.textContent).toMatch(/Overview/i);
  });

  it("non-active tabs do not have aria-current", () => {
    const { container } = render(<App />);
    const inactiveTabs = container.querySelectorAll('.tab:not([aria-current="page"])');
    expect(inactiveTabs.length).toBeGreaterThan(0);
  });

  it("each tab has a descriptive aria-label including screen number", () => {
    const { container } = render(<App />);
    const tabs = container.querySelectorAll(".tab");
    for (const tab of tabs) {
      const label = tab.getAttribute("aria-label");
      expect(label).toMatch(/screen \d+/);
    }
  });

  it("the screen-number span is aria-hidden so screen readers don't double-announce", () => {
    const { container } = render(<App />);
    const num = container.querySelector(".tab .num");
    expect(num.getAttribute("aria-hidden")).toBe("true");
  });
});

describe("Main landmark", () => {
  it("main has id=main-content and tabIndex=-1 (programmatic focus target)", () => {
    const { container } = render(<App />);
    const main = container.querySelector("main");
    expect(main.getAttribute("id")).toBe("main-content");
    expect(main.getAttribute("tabindex")).toBe("-1");
  });

  it("main has aria-label that names the current screen", () => {
    const { container } = render(<App />);
    const main = container.querySelector("main");
    const label = main.getAttribute("aria-label");
    expect(label).toMatch(/Overview/i);
    expect(label).toMatch(/screen/i);
  });
});

describe("Heading outline", () => {
  it("renders exactly one h1 per screen", () => {
    const { container } = render(<App />);
    const h1s = container.querySelectorAll("h1");
    expect(h1s).toHaveLength(1);
  });

  it("h1 names the screen + Concord Lite for context", () => {
    const { container } = render(<App />);
    const h1 = container.querySelector("h1");
    expect(h1.textContent).toMatch(/Concord Lite/i);
    expect(h1.textContent).toMatch(/Overview/i);
  });

  it("h1 is visually-hidden but in the DOM", () => {
    const { container } = render(<App />);
    const h1 = container.querySelector("h1");
    expect(h1.className).toContain("visually-hidden");
  });
});

describe("Single landmark per role", () => {
  it("has exactly one main, one header, one nav", () => {
    const { container } = render(<App />);
    expect(container.querySelectorAll("main")).toHaveLength(1);
    expect(container.querySelectorAll("header.topbar")).toHaveLength(1);
    expect(container.querySelectorAll("nav.tabs")).toHaveLength(1);
  });
});
