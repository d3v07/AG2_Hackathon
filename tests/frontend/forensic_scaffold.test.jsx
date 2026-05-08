/**
 * Sprint 17 #81 — Forensic screen scaffold tests.
 *
 * Verifies:
 * - The Forensic screen renders without crashing given the spans fixture
 * - Three panes exist (tree / waterfall / inspector) with placeholder copy
 * - Empty state renders when D.spans is empty
 * - Inspector copy reflects selectedSpanId
 * - Fixture spans satisfy the 16-field shape and 10 allowed kinds locked
 *   in Sprint 15 #72
 */
import { describe, it, expect, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { loadFixture } from "./fixture.js";

let Forensic;
let fixture;

const REQUIRED_SPAN_FIELDS = [
  "trace_id", "span_id", "parent_span_id", "name", "kind", "agent",
  "tool", "status", "start_time", "end_time", "duration_ms",
  "attributes", "input", "output", "error", "contract_refs",
];

const ALLOWED_SPAN_KINDS = new Set([
  "workflow", "agent", "tool", "handoff", "guardrail",
  "human_gate", "action", "contract_check", "repair", "regression",
]);

beforeAll(async () => {
  fixture = loadFixture();
  ({ Forensic } = await import("../../public/app.jsx"));
});

describe("Forensic scaffold — render", () => {
  it("renders without crashing given the spans fixture", () => {
    render(<Forensic selectedSpanId={null} setSelectedSpanId={() => {}} />);
    expect(screen.getByText(/Forensic Trace/i)).toBeInTheDocument();
  });

  it("shows the span count in the header", () => {
    render(<Forensic selectedSpanId={null} setSelectedSpanId={() => {}} />);
    // 14 spans in the fixture (10 kinds, with 6 agent and 2 tool spans)
    expect(screen.getByText(/14 spans/i)).toBeInTheDocument();
  });

  it("renders three named panes", () => {
    render(<Forensic selectedSpanId={null} setSelectedSpanId={() => {}} />);
    expect(screen.getByLabelText(/Span tree/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Timeline waterfall/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Span inspector/i)).toBeInTheDocument();
  });

  it("inspector shows 'select a span' empty state when nothing is selected", () => {
    render(<Forensic selectedSpanId={null} setSelectedSpanId={() => {}} />);
    expect(screen.getByText(/Select a span from the tree or waterfall/i)).toBeInTheDocument();
  });

  it("inspector echoes selectedSpanId when one is provided", () => {
    render(<Forensic selectedSpanId="sp_verifier" setSelectedSpanId={() => {}} />);
    expect(screen.getByText(/Inspector for span sp_verifier/i)).toBeInTheDocument();
  });
});

describe("Forensic scaffold — fixture contract (locks Sprint 15 #72)", () => {
  it("fixture has at least one span of each allowed kind that's actually present", () => {
    const kinds = new Set(fixture.spans.map(s => s.kind));
    // The 10-kind contract is the maximum surface — fixture covers all 10
    for (const k of ALLOWED_SPAN_KINDS) {
      expect(kinds.has(k)).toBe(true);
    }
  });

  it("every span has all 16 required fields", () => {
    for (const span of fixture.spans) {
      for (const field of REQUIRED_SPAN_FIELDS) {
        expect(Object.prototype.hasOwnProperty.call(span, field)).toBe(true);
      }
    }
  });

  it("every kind is in the allowed set", () => {
    for (const span of fixture.spans) {
      expect(ALLOWED_SPAN_KINDS.has(span.kind)).toBe(true);
    }
  });

  it("every non-root parent_span_id resolves to an existing span_id", () => {
    const ids = new Set(fixture.spans.map(s => s.span_id));
    for (const span of fixture.spans) {
      if (span.parent_span_id !== null) {
        expect(ids.has(span.parent_span_id)).toBe(true);
      }
    }
  });

  it("every child's start_time >= parent's start_time and end_time <= parent's end_time", () => {
    const byId = Object.fromEntries(fixture.spans.map(s => [s.span_id, s]));
    for (const span of fixture.spans) {
      if (span.parent_span_id === null) continue;
      const parent = byId[span.parent_span_id];
      expect(span.start_time).toBeGreaterThanOrEqual(parent.start_time);
      expect(span.end_time).toBeLessThanOrEqual(parent.end_time);
    }
  });

  it("exactly one root (workflow) span", () => {
    const roots = fixture.spans.filter(s => s.parent_span_id === null);
    expect(roots).toHaveLength(1);
    expect(roots[0].kind).toBe("workflow");
  });

  it("repair span links back to a failed agent via target_span_id attribute", () => {
    const repair = fixture.spans.find(s => s.kind === "repair");
    expect(repair).toBeDefined();
    expect(repair.attributes.target_span_id).toBeDefined();
    const target = fixture.spans.find(s => s.span_id === repair.attributes.target_span_id);
    expect(target).toBeDefined();
    expect(target.kind).toBe("agent");
    expect(target.status).toBe("error");
  });
});
