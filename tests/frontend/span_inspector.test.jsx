/**
 * Sprint 17 #84 — SpanInspector tests.
 *
 * Covers:
 * - Empty state when no span is selected
 * - Identity / Timing / Error sections rendering
 * - Collapsible Input / Output / Attributes blocks
 * - Contract violations section with deep-link handler
 * - Repair patches join via violation_id -> patch.violation
 * - Regression section for repair / regression spans + workflow fallback
 */
import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let SpanInspector;

beforeAll(async () => {
  loadFixture();
  ({ SpanInspector } = await import("../../public/app.jsx"));
});

const baseSpan = {
  trace_id: "tr_1",
  span_id: "sp_test",
  parent_span_id: "sp_root",
  name: "concord.agent.TestAgent",
  kind: "agent",
  agent: "TestAgent",
  tool: null,
  status: "ok",
  start_time: 1.234,
  end_time: 5.678,
  duration_ms: 4444,
  attributes: { "concord.step": 3, foo: "bar" },
  input: { task: "x" },
  output: { result: "y" },
  error: null,
  contract_refs: [],
};

const errorSpan = {
  ...baseSpan,
  span_id: "sp_err",
  status: "error",
  error: { type: "verification_failed", message: "0 sources verified" },
  contract_refs: [
    { contract_id: "C-EVD", violation_id: "V-001", severity: "HIGH", rule: "verified_sources_count > 0" },
    { contract_id: "C-TOL", violation_id: "V-002", severity: "HIGH", rule: "tool_call_id required" },
  ],
};

const samplePatches = [
  { id: "P-001", violation: "V-001", primitive: "Guardrail", title: "Add evidence Guardrail" },
  { id: "P-002", violation: "V-002", primitive: "ToolGate", title: "Require tool_event" },
  { id: "P-099", violation: "V-999", primitive: "Other", title: "Unrelated patch" },
];

const sampleRegressionRoot = {
  name: "test_run_041_contract_repair",
  test_status: "passed",
  sandbox_id: "dt-9f3a",
  duration_ms: 4128,
};

/* ─── Empty state ──────────────────────────────────────────────────────── */

describe("SpanInspector — empty state", () => {
  it("shows 'select a span' placeholder when span is null", () => {
    render(<SpanInspector span={null} allPatches={[]} regressionRoot={null} />);
    expect(screen.getByText(/Select a span from the tree or waterfall/i)).toBeInTheDocument();
  });
});

/* ─── Identity / Timing / Error ────────────────────────────────────────── */

describe("SpanInspector — identity & timing", () => {
  it("renders kind, status, name in the head", () => {
    const { container } = render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={null} />);
    expect(container.querySelector(".inspector-kind-label").textContent).toBe("agent");
    expect(container.querySelector(".inspector-status").textContent).toBe("ok");
    expect(screen.getByText(/agent\.TestAgent/i)).toBeInTheDocument();
  });

  it("renders span_id, parent_span_id, trace_id, agent in Identity", () => {
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={null} />);
    expect(screen.getByText("sp_test")).toBeInTheDocument();
    expect(screen.getByText("sp_root")).toBeInTheDocument();
    expect(screen.getByText("tr_1")).toBeInTheDocument();
    expect(screen.getByText("TestAgent")).toBeInTheDocument();
  });

  it("renders root span as '(root)' when parent_span_id is null", () => {
    render(<SpanInspector span={{ ...baseSpan, parent_span_id: null }} allPatches={[]} regressionRoot={null} />);
    expect(screen.getByText(/\(root\)/)).toBeInTheDocument();
  });

  it("renders timing in seconds and ms", () => {
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={null} />);
    expect(screen.getByText("1.234s")).toBeInTheDocument();
    expect(screen.getByText("5.678s")).toBeInTheDocument();
    expect(screen.getByText("4444ms")).toBeInTheDocument();
  });

  it("does NOT render Error section when span has no error", () => {
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={null} />);
    expect(screen.queryByRole("heading", { name: /^Error$/ })).toBeNull();
  });

  it("renders Error section when span has error type/message", () => {
    render(<SpanInspector span={errorSpan} allPatches={[]} regressionRoot={null} />);
    expect(screen.getByRole("heading", { name: /^Error$/ })).toBeInTheDocument();
    expect(screen.getByText("verification_failed")).toBeInTheDocument();
    expect(screen.getByText(/0 sources verified/)).toBeInTheDocument();
  });
});

/* ─── Collapsible blocks ───────────────────────────────────────────────── */

describe("SpanInspector — collapsible blocks", () => {
  it("Input/Output/Attributes blocks start collapsed", () => {
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={null} />);
    const inputToggle = screen.getByRole("button", { name: /^Input/i });
    expect(inputToggle.getAttribute("aria-expanded")).toBe("false");
  });

  it("clicking a block toggle expands it and reveals JSON", () => {
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={null} />);
    fireEvent.click(screen.getByRole("button", { name: /^Input/i }));
    expect(screen.getByText(/"task"/)).toBeInTheDocument();
  });

  it("Attributes title includes the count", () => {
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={null} />);
    expect(screen.getByRole("button", { name: /Attributes \(2\)/ })).toBeInTheDocument();
  });
});

/* ─── Contract violations ──────────────────────────────────────────────── */

describe("SpanInspector — contract violations", () => {
  it("does not render violations section when contract_refs is empty", () => {
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={null} />);
    expect(screen.queryByRole("heading", { name: /Contract violations/i })).toBeNull();
  });

  it("renders one row per contract_ref with contract_id + severity + rule", () => {
    render(<SpanInspector span={errorSpan} allPatches={[]} regressionRoot={null} />);
    expect(screen.getByRole("heading", { name: /Contract violations \(2\)/i })).toBeInTheDocument();
    expect(screen.getByText("C-EVD")).toBeInTheDocument();
    expect(screen.getByText("C-TOL")).toBeInTheDocument();
  });

  it("clicking a violation row calls onJumpToScreen('violations')", () => {
    const onJump = vi.fn();
    render(<SpanInspector span={errorSpan} allPatches={[]} regressionRoot={null} onJumpToScreen={onJump} />);
    fireEvent.click(screen.getByRole("button", { name: /View violation V-001 on Violations screen/i }));
    expect(onJump).toHaveBeenCalledWith("violations");
  });
});

/* ─── Repair patches join ─────────────────────────────────────────────── */

describe("SpanInspector — repair patches", () => {
  it("joins patches via contract_refs.violation_id == patch.violation", () => {
    render(<SpanInspector span={errorSpan} allPatches={samplePatches} regressionRoot={null} />);
    expect(screen.getByRole("heading", { name: /Repair \(2\)/i })).toBeInTheDocument();
    expect(screen.getByText("P-001")).toBeInTheDocument();
    expect(screen.getByText("P-002")).toBeInTheDocument();
    expect(screen.queryByText("P-099")).toBeNull();
  });

  it("does not render Repair section when no patches match", () => {
    render(<SpanInspector span={baseSpan} allPatches={samplePatches} regressionRoot={null} />);
    expect(screen.queryByRole("heading", { name: /Repair/i })).toBeNull();
  });

  it("clicking a patch row calls onJumpToScreen('repair')", () => {
    const onJump = vi.fn();
    render(<SpanInspector span={errorSpan} allPatches={samplePatches} regressionRoot={null} onJumpToScreen={onJump} />);
    fireEvent.click(screen.getByRole("button", { name: /Open patch P-001 on Repair screen/i }));
    expect(onJump).toHaveBeenCalledWith("repair");
  });
});

/* ─── Regression linkage ──────────────────────────────────────────────── */

describe("SpanInspector — regression linkage", () => {
  it("regression span itself is shown directly", () => {
    const regressionSpan = {
      ...baseSpan,
      span_id: "sp_reg",
      kind: "regression",
      status: "ok",
      duration_ms: 1700,
      attributes: { sandbox_id: "dt-xxx", test_status: "passed", test_name: "test_X" },
    };
    render(<SpanInspector span={regressionSpan} allPatches={[]} regressionRoot={null} />);
    expect(screen.getByRole("heading", { name: /^Regression$/i })).toBeInTheDocument();
    expect(screen.getByText("test_X")).toBeInTheDocument();
    expect(screen.getByText("dt-xxx")).toBeInTheDocument();
  });

  it("falls back to the workflow-level regression when span itself is not a regression", () => {
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={sampleRegressionRoot} />);
    expect(screen.getByText(/test_run_041_contract_repair/i)).toBeInTheDocument();
    expect(screen.getByText("dt-9f3a")).toBeInTheDocument();
  });

  it("does not render Regression section when neither span nor root is regression-shaped", () => {
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={null} />);
    expect(screen.queryByRole("heading", { name: /^Regression$/i })).toBeNull();
  });

  it("'Open on Regression screen' calls onJumpToScreen('regression')", () => {
    const onJump = vi.fn();
    render(<SpanInspector span={baseSpan} allPatches={[]} regressionRoot={sampleRegressionRoot} onJumpToScreen={onJump} />);
    fireEvent.click(screen.getByRole("button", { name: /Open on Regression screen/i }));
    expect(onJump).toHaveBeenCalledWith("regression");
  });
});
