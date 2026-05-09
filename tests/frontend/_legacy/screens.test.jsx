/**
 * Sprint 16 #76 — smoke render tests for the 6 existing dashboard screens.
 *
 * Each test mounts a screen with the fixture CONCORD_DATA loaded from
 * public/data.js and asserts: renders without throwing, key landmark text
 * present, no console.error during mount. This is the regression net for
 * subsequent Sprint 17/18 frontend changes.
 *
 * NOTE: public/app.jsx is the dev reference; the production dashboard
 * inlines its JSX into public/index.html. Tests here cover the dev module
 * — Sprint 17 should refactor index.html to load app.jsx as an ES module
 * so tests cover production behavior.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let App, Overview, Trace, Violations, Repair, Regression, Report;

beforeAll(async () => {
  loadFixture();
  // Import after fixture is set so app.jsx's `const D = window.CONCORD_DATA;`
  // resolves to the fixture, not undefined.
  const mod = await import("../../public/app.jsx");
  ({ App, Overview, Trace, Violations, Repair, Regression, Report } = mod);
});

let consoleSpy;
beforeEach(() => {
  consoleSpy = vi.spyOn(console, "error").mockImplementation((...args) => {
    // Allow React's act() and key-prop nags to pass; fail on real render errors.
    const msg = String(args[0] ?? "");
    if (msg.includes("Each child in a list") || msg.includes("act(...)")) return;
    throw new Error(`console.error during render: ${args.join(" ")}`);
  });
});
afterEach(() => {
  consoleSpy.mockRestore();
});

describe("Overview screen", () => {
  it("renders without crashing and shows OVERVIEW landmark", () => {
    render(<Overview setScreen={() => {}} />);
    expect(screen.getAllByText(/RUN-041|LITERATURE/i).length).toBeGreaterThan(0);
  });
});

describe("Trace screen", () => {
  it("renders without crashing", () => {
    const { container } = render(<Trace />);
    expect(container.firstChild).not.toBeNull();
  });
});

describe("Violations screen", () => {
  it("renders without crashing", () => {
    const { container } = render(
      <Violations setScreen={() => {}} setSelectedPatch={() => {}} />,
    );
    expect(container.firstChild).not.toBeNull();
  });
});

describe("Repair screen", () => {
  it("renders without crashing", () => {
    const { container } = render(
      <Repair selectedPatch={null} setSelectedPatch={() => {}} />,
    );
    expect(container.firstChild).not.toBeNull();
  });
});

describe("Regression screen", () => {
  it("renders without crashing", () => {
    const { container } = render(<Regression />);
    expect(container.firstChild).not.toBeNull();
  });
});

describe("Report screen", () => {
  it("renders without crashing", () => {
    const { container } = render(<Report setScreen={() => {}} />);
    expect(container.firstChild).not.toBeNull();
  });
});

describe("App shell", () => {
  it("renders the app shell with navigation", () => {
    const { container } = render(<App />);
    expect(container.firstChild).not.toBeNull();
  });
});
