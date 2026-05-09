/**
 * Sprint 17 #82 — SpanTree tests.
 *
 * Covers:
 * - Tree structure built from parent_span_id
 * - Click sets selectedSpanId
 * - Selected span gets aria-selected and visible highlight
 * - Collapse/expand via chevron and keyboard
 * - Keyboard navigation (arrow up/down/left/right, enter, space)
 * - Violation badge rendering when contract_refs is non-empty
 * - Failed status surfaces err class
 */
import { describe, it, expect, beforeAll, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let SpanTree;

beforeAll(async () => {
  loadFixture();
  ({ SpanTree } = await import("../../public/app.jsx"));
});

const sampleSpans = [
  {
    trace_id: "tr_1", span_id: "sp_root", parent_span_id: null,
    name: "concord.workflow.X", kind: "workflow",
    agent: null, tool: null, status: "ok",
    start_time: 0, end_time: 5, duration_ms: 5000,
    attributes: {}, input: {}, output: {}, error: null, contract_refs: [],
  },
  {
    trace_id: "tr_1", span_id: "sp_a", parent_span_id: "sp_root",
    name: "concord.agent.A", kind: "agent",
    agent: "AgentA", tool: null, status: "ok",
    start_time: 0.1, end_time: 2, duration_ms: 1900,
    attributes: {}, input: {}, output: {}, error: null, contract_refs: [],
  },
  {
    trace_id: "tr_1", span_id: "sp_a_tool", parent_span_id: "sp_a",
    name: "concord.tool.t1", kind: "tool",
    agent: "AgentA", tool: "t1", status: "ok",
    start_time: 0.2, end_time: 0.5, duration_ms: 300,
    attributes: {}, input: {}, output: {}, error: null, contract_refs: [],
  },
  {
    trace_id: "tr_1", span_id: "sp_b", parent_span_id: "sp_root",
    name: "concord.agent.B", kind: "agent",
    agent: "AgentB", tool: null, status: "error",
    start_time: 2, end_time: 4, duration_ms: 2000,
    attributes: {}, input: {}, output: {}, error: { type: "x" },
    contract_refs: [
      { contract_id: "C-EVD", violation_id: "V-001", severity: "HIGH", rule: "verified > 0" },
      { contract_id: "C-TOL", violation_id: "V-002", severity: "HIGH", rule: "tool_call_id required" },
    ],
  },
];

describe("SpanTree — structure", () => {
  it("renders one row per span when fully expanded by default", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const rows = screen.getAllByRole("treeitem");
    expect(rows).toHaveLength(4);
  });

  it("indents children based on depth via aria-level", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const root = screen.getAllByRole("treeitem")[0];
    expect(root.getAttribute("aria-level")).toBe("1");
    const childA = screen.getAllByRole("treeitem")[1];
    expect(childA.getAttribute("aria-level")).toBe("2");
    const grandchild = screen.getAllByRole("treeitem")[2];
    expect(grandchild.getAttribute("aria-level")).toBe("3");
  });

  it("orphan spans (parent_span_id pointing to nothing) are placed at root", () => {
    const orphans = [
      { ...sampleSpans[1], span_id: "orphan", parent_span_id: "DOES_NOT_EXIST" },
    ];
    render(<SpanTree spans={orphans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const rows = screen.getAllByRole("treeitem");
    expect(rows[0].getAttribute("aria-level")).toBe("1");
  });

  it("renders nothing-to-render placeholder when spans is empty", () => {
    render(<SpanTree spans={[]} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    expect(screen.getByText(/No spans to render/i)).toBeInTheDocument();
    expect(screen.queryByRole("tree")).toBeNull();
  });
});

describe("SpanTree — selection", () => {
  it("clicking a row calls setSelectedSpanId with that span_id", () => {
    const setSelected = vi.fn();
    render(<SpanTree spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={setSelected} />);

    fireEvent.click(screen.getByText(/agent\.B/));
    expect(setSelected).toHaveBeenCalledWith("sp_b");
  });

  it("the selected row has aria-selected=true and a selected class", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId="sp_a" setSelectedSpanId={() => {}} />);
    const selected = screen.getAllByRole("treeitem").find(r => r.getAttribute("data-span-id") === "sp_a");
    expect(selected.getAttribute("aria-selected")).toBe("true");
    expect(selected.className).toContain("selected");
  });
});

describe("SpanTree — collapse/expand", () => {
  it("clicking the chevron collapses the subtree", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const rootRow = screen.getAllByRole("treeitem")[0];
    const chevron = within(rootRow).getByRole("button");
    fireEvent.click(chevron);
    // root should now show only itself
    const rows = screen.getAllByRole("treeitem");
    expect(rows).toHaveLength(1);
  });

  it("re-expanding restores the children", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const rootRow = screen.getAllByRole("treeitem")[0];
    const chevron = within(rootRow).getByRole("button");
    fireEvent.click(chevron); // collapse
    fireEvent.click(screen.getAllByRole("treeitem")[0].querySelector("button")); // expand
    expect(screen.getAllByRole("treeitem")).toHaveLength(4);
  });

  it("leaf spans (no children) have a chevron spacer instead of a button", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const tool = screen.getAllByRole("treeitem").find(r => r.getAttribute("data-span-id") === "sp_a_tool");
    expect(within(tool).queryByRole("button")).toBeNull();
  });
});

describe("SpanTree — keyboard navigation", () => {
  it("ArrowDown moves selection to the next visible row", () => {
    const setSelected = vi.fn();
    render(<SpanTree spans={sampleSpans} selectedSpanId="sp_root" setSelectedSpanId={setSelected} />);
    const tree = screen.getByRole("tree");
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    expect(setSelected).toHaveBeenCalledWith("sp_a");
  });

  it("ArrowUp moves selection to the previous visible row", () => {
    const setSelected = vi.fn();
    render(<SpanTree spans={sampleSpans} selectedSpanId="sp_a" setSelectedSpanId={setSelected} />);
    fireEvent.keyDown(screen.getByRole("tree"), { key: "ArrowUp" });
    expect(setSelected).toHaveBeenCalledWith("sp_root");
  });

  it("Enter on a parent toggles its expansion", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId="sp_root" setSelectedSpanId={() => {}} />);
    fireEvent.keyDown(screen.getByRole("tree"), { key: "Enter" });
    // collapsing root removes children
    expect(screen.getAllByRole("treeitem")).toHaveLength(1);
  });

  it("Space selects the currently-highlighted span (no-op for already selected)", () => {
    const setSelected = vi.fn();
    render(<SpanTree spans={sampleSpans} selectedSpanId="sp_a" setSelectedSpanId={setSelected} />);
    fireEvent.keyDown(screen.getByRole("tree"), { key: " " });
    expect(setSelected).toHaveBeenCalledWith("sp_a");
  });
});

describe("SpanTree — violation badge & error styling", () => {
  it("renders the violation count badge when contract_refs is non-empty", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const badged = screen.getAllByRole("treeitem").find(r => r.getAttribute("data-span-id") === "sp_b");
    expect(within(badged).getByText("2")).toBeInTheDocument();
    expect(within(badged).getByLabelText(/2 violations/i)).toBeInTheDocument();
  });

  it("does not render a badge when contract_refs is empty", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const okSpan = screen.getAllByRole("treeitem").find(r => r.getAttribute("data-span-id") === "sp_a");
    expect(within(okSpan).queryByText(/^\d+$/)).toBeNull();
  });

  it("error-status spans get the err class on the row", () => {
    render(<SpanTree spans={sampleSpans} selectedSpanId={null} setSelectedSpanId={() => {}} />);
    const errSpan = screen.getAllByRole("treeitem").find(r => r.getAttribute("data-span-id") === "sp_b");
    expect(errSpan.className).toContain("err");
  });
});
