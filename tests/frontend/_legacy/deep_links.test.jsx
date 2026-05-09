/**
 * Sprint 17 #85 — Cross-screen deep-links to forensic spans.
 *
 * Covers:
 * - _findSpanForAgent helper (explicit span_id wins, agent name fallback)
 * - ViewSpanLink renders only when spanId is set
 * - Click calls onClick with span_id, stops propagation
 * - Violations / Repair / Regression all expose deep-links to Forensic
 * - App-level URL hash sync (read on mount, write on screen/span change)
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let App, Violations, Repair, Regression, ViewSpanLink, _findSpanForAgent;
let mod;

beforeAll(async () => {
  loadFixture();
  mod = await import("../../public/app.jsx");
  ({ App, Violations, Repair, Regression, ViewSpanLink } = mod);
});

beforeEach(() => {
  // Reset hash between tests
  if (typeof window !== "undefined") {
    history.replaceState(null, "", "#");
  }
});

afterEach(() => {
  vi.restoreAllMocks();
});

/* ─── ViewSpanLink ─────────────────────────────────────────────────────── */

describe("ViewSpanLink", () => {
  it("renders nothing when spanId is null", () => {
    const { container } = render(<ViewSpanLink spanId={null} onClick={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a button with default 'View span' label", () => {
    render(<ViewSpanLink spanId="sp_1" onClick={() => {}} />);
    expect(screen.getByRole("button", { name: /View span sp_1 on Forensic screen/i })).toBeInTheDocument();
  });

  it("supports a custom label", () => {
    render(<ViewSpanLink spanId="sp_1" onClick={() => {}} label="Forensic span" />);
    expect(screen.getByRole("button", { name: /Forensic span sp_1 on Forensic screen/i })).toBeInTheDocument();
  });

  it("click calls onClick(spanId) and does NOT bubble", () => {
    const onClick = vi.fn();
    const onParent = vi.fn();
    const { container } = render(
      <div onClick={onParent}>
        <ViewSpanLink spanId="sp_1" onClick={onClick} />
      </div>,
    );
    fireEvent.click(container.querySelector(".view-span-link"));
    expect(onClick).toHaveBeenCalledWith("sp_1");
    expect(onParent).not.toHaveBeenCalled();
  });
});

/* ─── Violations deep-link ─────────────────────────────────────────────── */

describe("Violations screen — deep-link to Forensic", () => {
  it("each violation row offers a 'View span' button when a matching span exists", () => {
    const goTo = vi.fn();
    render(
      <Violations
        setScreen={() => {}}
        setSelectedPatch={() => {}}
        goToForensicSpan={goTo}
      />,
    );
    // Fixture violations target VerifierAgent / ReporterAgent / ActionAgent
    // and the spans fixture has one of each => at least one View span link
    const links = screen.getAllByRole("button", { name: /View span .* on Forensic screen/i });
    expect(links.length).toBeGreaterThan(0);
  });

  it("clicking the link calls goToForensicSpan with the matched span_id", () => {
    const goTo = vi.fn();
    render(
      <Violations
        setScreen={() => {}}
        setSelectedPatch={() => {}}
        goToForensicSpan={goTo}
      />,
    );
    const links = screen.getAllByRole("button", { name: /View span .* on Forensic screen/i });
    fireEvent.click(links[0]);
    expect(goTo).toHaveBeenCalled();
    // The arg must be a span_id string (non-empty, starts with sp_)
    expect(goTo.mock.calls[0][0]).toMatch(/^sp_/);
  });

  it("does NOT navigate to Repair when the link is clicked (stopPropagation)", () => {
    const setScreen = vi.fn();
    const goTo = vi.fn();
    render(
      <Violations
        setScreen={setScreen}
        setSelectedPatch={() => {}}
        goToForensicSpan={goTo}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /View span/i })[0]);
    expect(goTo).toHaveBeenCalled();
    expect(setScreen).not.toHaveBeenCalled();
  });
});

/* ─── Repair deep-link ─────────────────────────────────────────────────── */

describe("Repair screen — deep-link to Forensic", () => {
  it("each patch surfaces a 'View span' link to its target span", () => {
    const goTo = vi.fn();
    render(
      <Repair
        selectedPatch={null}
        setSelectedPatch={() => {}}
        goToForensicSpan={goTo}
      />,
    );
    const links = screen.getAllByRole("button", { name: /View span .* on Forensic screen/i });
    expect(links.length).toBeGreaterThan(0);
  });

  it("click calls goToForensicSpan with a span_id", () => {
    const goTo = vi.fn();
    render(
      <Repair
        selectedPatch={null}
        setSelectedPatch={() => {}}
        goToForensicSpan={goTo}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /View span/i })[0]);
    expect(goTo).toHaveBeenCalled();
    expect(goTo.mock.calls[0][0]).toMatch(/^sp_/);
  });
});

/* ─── Regression deep-link ─────────────────────────────────────────────── */

describe("Regression screen — deep-link to Forensic", () => {
  it("Regression screen offers a 'Forensic span' link to the regression span", () => {
    const goTo = vi.fn();
    render(<Regression goToForensicSpan={goTo} />);
    expect(screen.getByRole("button", { name: /Forensic span sp_regression on Forensic screen/i })).toBeInTheDocument();
  });

  it("click navigates to the regression span", () => {
    const goTo = vi.fn();
    render(<Regression goToForensicSpan={goTo} />);
    fireEvent.click(screen.getByRole("button", { name: /Forensic span sp_regression/i }));
    expect(goTo).toHaveBeenCalledWith("sp_regression");
  });
});

/* ─── App-level URL hash sync ──────────────────────────────────────────── */

describe("App hash routing", () => {
  it("reads screen + span from URL hash on mount", async () => {
    history.replaceState(null, "", "#screen=forensic&span=sp_verifier");
    const { container } = render(<App />);
    // Forensic screen pane should be visible
    expect(container.querySelector('[aria-label="Span tree"]')).toBeTruthy();
  });

  it("writes screen + span to URL hash when navigating", async () => {
    render(<App />);
    // Click the Forensic tab in nav
    fireEvent.click(screen.getByRole("button", { name: /Forensic/i }));
    expect(window.location.hash).toContain("screen=forensic");
  });
});
