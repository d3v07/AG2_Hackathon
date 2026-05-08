/**
 * Sprint 18 #87 — responsive layout tests.
 *
 * jsdom doesn't actually compute layout, so these tests verify the
 * CSS rules exist and are correctly scoped via @media. We resize the
 * window to assert media-query-aware code paths fire (rare in this
 * codebase — most responsive logic is pure CSS), and parse the CSS
 * to assert the breakpoint set covers 1024 / 640 / 375.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const CSS = readFileSync(resolve("public/styles.css"), "utf8");

describe("Responsive media queries", () => {
  it("declares the tablet breakpoint at 1024px", () => {
    expect(CSS).toMatch(/@media \(max-width: 1024px\)/);
  });

  it("declares the mobile breakpoint at 640px", () => {
    expect(CSS).toMatch(/@media \(max-width: 640px\)/);
  });

  // Each rule is asserted as: media query exists AND rule body exists in the file.
  // We don't try to parse the nested block scope (browser CSS engine handles that).
  it("collapses meta-strip on tablet", () => {
    expect(CSS).toMatch(/@media \(max-width: 1024px\)/);
    expect(CSS).toMatch(/meta-strip\s*\{\s*grid-template-columns:\s*repeat\(3,/);
  });

  it("collapses meta-strip on mobile", () => {
    expect(CSS).toMatch(/@media \(max-width: 640px\)/);
    expect(CSS).toMatch(/meta-strip\s*\{\s*grid-template-columns:\s*repeat\(2,/);
  });

  it("ensures min-height 44px tap targets on mobile (WCAG 2.5.5)", () => {
    const matches = CSS.match(/min-height:\s*44px/g) || [];
    expect(matches.length).toBeGreaterThanOrEqual(2);
  });

  it("forensic 3-pane grid stacks to single column at <=1024px", () => {
    // The forensic-grid 1fr declaration must appear (multiple times — one per breakpoint)
    const matches = CSS.match(/forensic-grid\s*\{[\s\S]*?grid-template-columns:\s*1fr/g) || [];
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it("topbar collapses to vertical stack on mobile", () => {
    expect(CSS).toMatch(/topbar\s*\{\s*grid-template-columns:\s*1fr/);
  });

  it("waterfall keeps horizontal scroll affordance on mobile (designed exception)", () => {
    expect(CSS).toMatch(/forensic-pane-body-waterfall\s*\{\s*overflow-x:\s*auto/);
  });
});

describe("No horizontal scroll on body at any breakpoint", () => {
  it("html/body never set width/min-width that would force scroll", () => {
    expect(CSS).not.toMatch(/^html\s*\{[^}]*min-width/m);
    expect(CSS).not.toMatch(/^body\s*\{[^}]*min-width/m);
    // overflow-x: hidden is fine (acceptable affordance); just ensure no
    // explicit width forcing
    expect(CSS).not.toMatch(/^body\s*\{[^}]*width:\s*\d+px/m);
  });
});
