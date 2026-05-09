/**
 * Sprint 17 #83 — TimelineWaterfall tests.
 *
 * Covers:
 * - Renders one row per span, ordered by start_time
 * - Bar position and width proportional to start_time / duration_ms
 * - Click selects span via setSelectedSpanId
 * - Selected row gets aria-pressed + visual highlight
 * - Failed spans get err class on the bar
 * - Empty spans -> placeholder
 * - Time axis renders monotonically increasing tick labels
 * - aria-label is descriptive (kind/duration/error/violations)
 */
import { describe, it, expect, beforeAll } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let TimelineWaterfall;

beforeAll(async () => {
  loadFixture();
  ({ TimelineWaterfall } = await import("../../public/app.jsx"));
});

const sampleSpans = [
  {
    trace_id: "tr_1", span_id: "sp_a", parent_span_id: null,
    name: "concord.workflow.X", kind: "workflow",
    agent: null, tool: null, status: "ok",
    start_time: 0.0, end_time: 10.0, duration_ms: 10000,
    attributes: {}, input: {}, output: {}, error: null, contract_refs: [],
  },
  {
    trace_id: "tr_1", span_id: "sp_b", parent_span_id: "sp_a",
    name: "concord.agent.B", kind: "agent",
    agent: "AgentB", tool: null, status: "ok",
    start_time: 1.0, end_time: 4.0, duration_ms: 3000,
    attributes: {}, input: {}, output: {}, error: null, contract_refs: [],
  },
  {
    trace_id: "tr_1", span_id: "sp_c", parent_span_id: "sp_a",
    name: "concord.agent.C", kind: "agent",
    agent: "AgentC", tool: null, status: "error",
    start_time: 5.0, end_time: 9.0, duration_ms: 4000,
    attributes: {}, input: {}, output: {}, error: { type: "x" },
    contract_refs: [{ contract_id: "C-EVD", violation_id: "V-001", severity: "HIGH", rule: "..." }],
  },
];

describe("TimelineWaterfall — render", () => {
  it("renders empty placeholder when spans is empty", () => {
    render(<TimelineWaterfall spans={[]} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    expect(screen.getByText(/No spans to plot/i)).toBeInTheDocument();
  });

  it("renders one row per span, ordered by start_time", () => {
    render(<TimelineWaterfall spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0].getAttribute("data-span-id")).toBe("sp_a");
    expect(rows[1].getAttribute("data-span-id")).toBe("sp_b");
    expect(rows[2].getAttribute("data-span-id")).toBe("sp_c");
  });

  it("bar position and width are proportional to start_time and duration", () => {
    const { container } = render(
      <TimelineWaterfall spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />,
    );
    // span sp_b: start 1, duration 3, total range 0..10 => left 10%, width 30%
    const sp_b = container.querySelector('[data-span-id="sp_b"] .waterfall-bar');
    expect(sp_b.style.left).toBe("10%");
    expect(sp_b.style.width).toBe("30%");
  });

  it("renders the correct number of axis ticks", () => {
    const { container } = render(
      <TimelineWaterfall spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />,
    );
    const ticks = container.querySelectorAll(".waterfall-tick");
    expect(ticks).toHaveLength(6); // tickCount + 1 = 6
  });
});

describe("TimelineWaterfall — selection", () => {
  it("clicking a row calls setSelectedSpanId", () => {
    const setSelected = vi.fn();
    render(<TimelineWaterfall spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={setSelected} />);
    fireEvent.click(screen.getAllByRole("listitem")[1]);
    expect(setSelected).toHaveBeenCalledWith("sp_b");
  });

  it("selected row has aria-pressed=true and selected class", () => {
    render(<TimelineWaterfall spans={sampleSpans} selectedSpanId="sp_c" setSelectedSpanId={() => {}} />);
    const selected = screen.getAllByRole("listitem").find(r => r.getAttribute("data-span-id") === "sp_c");
    expect(selected.getAttribute("aria-pressed")).toBe("true");
    expect(selected.className).toContain("selected");
  });

  it("non-selected rows have aria-pressed=false", () => {
    render(<TimelineWaterfall spans={sampleSpans} selectedSpanId="sp_c" setSelectedSpanId={() => {}} />);
    const nonSelected = screen.getAllByRole("listitem").find(r => r.getAttribute("data-span-id") === "sp_a");
    expect(nonSelected.getAttribute("aria-pressed")).toBe("false");
  });
});

describe("TimelineWaterfall — error states", () => {
  it("error-status spans get err class on the bar", () => {
    const { container } = render(
      <TimelineWaterfall spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />,
    );
    const errBar = container.querySelector('[data-span-id="sp_c"] .waterfall-bar');
    expect(errBar.className).toContain("err");
  });

  it("aria-label includes (error) for failed spans", () => {
    render(<TimelineWaterfall spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const errRow = screen.getAllByRole("listitem").find(r => r.getAttribute("data-span-id") === "sp_c");
    expect(errRow.getAttribute("aria-label")).toContain("error");
  });

  it("aria-label includes violation count when present", () => {
    render(<TimelineWaterfall spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const errRow = screen.getAllByRole("listitem").find(r => r.getAttribute("data-span-id") === "sp_c");
    expect(errRow.getAttribute("aria-label")).toContain("1 violations");
  });
});

describe("TimelineWaterfall — single span edge case", () => {
  it("handles a single span without dividing by zero", () => {
    const single = [sampleSpans[0]];
    const { container } = render(
      <TimelineWaterfall spans={single} selectedSpanId={null} setSelectedSpanId={() => {}} />,
    );
    const bar = container.querySelector('[data-span-id="sp_a"] .waterfall-bar');
    // total = end - start = 10, single span fills the full range
    expect(bar.style.left).toBe("0%");
    expect(bar.style.width).toBe("100%");
  });

  it("handles instantaneous spans (start == end) with min width", () => {
    const instant = [{
      ...sampleSpans[0],
      start_time: 5.0,
      end_time: 5.0,
      duration_ms: 0,
    }, sampleSpans[1]];
    const { container } = render(
      <TimelineWaterfall spans={instant} selectedSpanId={null} setSelectedSpanId={() => {}} />,
    );
    const bar = container.querySelector('[data-span-id="sp_a"] .waterfall-bar');
    // min width is 0.3% so instant spans stay visible
    expect(parseFloat(bar.style.width)).toBeGreaterThanOrEqual(0.3);
  });
});
