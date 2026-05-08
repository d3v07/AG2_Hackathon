"""Sprint 15 #73 — ConcordSpanExporter.to_spans_payload() shape tests.

Asserts the 16-field span shape, allowed kinds, parent reference resolution,
and the synthesized workflow root span.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# concord_sdk is a sibling package under sdk/ — make it importable in tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk"))


REQUIRED_SPAN_FIELDS = {
    "trace_id",
    "span_id",
    "parent_span_id",
    "name",
    "kind",
    "agent",
    "tool",
    "status",
    "start_time",
    "end_time",
    "duration_ms",
    "attributes",
    "input",
    "output",
    "error",
    "contract_refs",
}

ALLOWED_SPAN_KINDS = {
    "workflow",
    "agent",
    "tool",
    "handoff",
    "guardrail",
    "human_gate",
    "action",
    "contract_check",
    "repair",
    "regression",
}


def _build_exporter_and_emit(spans_to_emit):
    """Helper: spin up a TracerProvider + ConcordSpanExporter and emit the given spans."""
    from zone_a.trace_adapter import ConcordSpanExporter

    exporter = ConcordSpanExporter(run_id="run_test", workflow_name="TestWorkflow")
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("concord.test")

    for span_attrs in spans_to_emit:
        with tracer.start_as_current_span(
            span_attrs.pop("__name__", "concord.span"),
            attributes=span_attrs,
        ):
            pass
    provider.force_flush()
    return exporter


# ─── empty case ────────────────────────────────────────────────────────────────


def test_to_spans_payload_returns_empty_list_when_no_spans():
    from zone_a.trace_adapter import ConcordSpanExporter

    exporter = ConcordSpanExporter(run_id="run_empty", workflow_name="Empty")
    assert exporter.to_spans_payload() == []


# ─── 16-field shape ───────────────────────────────────────────────────────────


def test_every_span_has_exact_16_fields():
    exporter = _build_exporter_and_emit(
        [
            {
                "__name__": "concord.agent.Researcher",
                "concord.kind": "agent",
                "concord.agent": "ResearcherAgent",
                "ag2.span.type": "agent",
            },
            {
                "__name__": "concord.tool.tavily",
                "concord.kind": "tool",
                "concord.agent": "ResearcherAgent",
                "gen_ai.tool.name": "tavily_search",
                "ag2.span.type": "tool",
            },
        ]
    )
    spans = exporter.to_spans_payload()
    assert len(spans) >= 2  # synthesized root + 2 emitted

    for span in spans:
        actual = set(span.keys())
        missing = REQUIRED_SPAN_FIELDS - actual
        extra = actual - REQUIRED_SPAN_FIELDS
        assert not missing, f"span {span.get('name')!r} missing fields: {missing}"
        assert not extra, f"span {span.get('name')!r} has unexpected fields: {extra}"


# ─── 10 allowed kinds ─────────────────────────────────────────────────────────


def test_kind_is_in_allowed_set():
    exporter = _build_exporter_and_emit(
        [
            {"__name__": "agent", "concord.kind": "agent", "concord.agent": "X", "ag2.span.type": "agent"},
            {"__name__": "tool", "concord.kind": "tool", "concord.agent": "X", "ag2.span.type": "tool"},
            {"__name__": "handoff", "concord.kind": "handoff", "concord.agent": "X", "ag2.span.type": "handoff"},
            {"__name__": "guardrail", "concord.kind": "guardrail", "concord.agent": "X"},
            {"__name__": "human_gate", "concord.kind": "human_gate", "concord.agent": "HumanGate"},
        ]
    )
    spans = exporter.to_spans_payload()
    for span in spans:
        assert span["kind"] in ALLOWED_SPAN_KINDS


# ─── synthesized workflow root ────────────────────────────────────────────────


def test_workflow_root_span_synthesized():
    exporter = _build_exporter_and_emit(
        [{"__name__": "agent.a", "concord.kind": "agent", "concord.agent": "A", "ag2.span.type": "agent"}]
    )
    spans = exporter.to_spans_payload()

    roots = [s for s in spans if s["parent_span_id"] is None]
    assert len(roots) == 1
    root = roots[0]
    assert root["kind"] == "workflow"
    assert root["span_id"].startswith("sp_workflow")
    assert "TestWorkflow" in root["name"]
    assert root["attributes"]["workflow.name"] == "TestWorkflow"
    assert root["attributes"]["run.id"] == "run_test"


# ─── parent references all resolve ────────────────────────────────────────────


def test_every_parent_reference_resolves():
    exporter = _build_exporter_and_emit(
        [
            {"__name__": "a", "concord.kind": "agent", "concord.agent": "A", "ag2.span.type": "agent"},
            {"__name__": "b", "concord.kind": "agent", "concord.agent": "B", "ag2.span.type": "agent"},
        ]
    )
    spans = exporter.to_spans_payload()
    span_ids = {s["span_id"] for s in spans}
    for s in spans:
        if s["parent_span_id"] is not None:
            assert s["parent_span_id"] in span_ids, (
                f"span {s['name']} has unresolved parent {s['parent_span_id']}"
            )


# ─── timestamps monotonic within parent ───────────────────────────────────────


def test_child_timestamps_within_synthesized_root():
    exporter = _build_exporter_and_emit(
        [
            {"__name__": "a", "concord.kind": "agent", "concord.agent": "A", "ag2.span.type": "agent"},
            {"__name__": "b", "concord.kind": "agent", "concord.agent": "B", "ag2.span.type": "agent"},
        ]
    )
    spans = exporter.to_spans_payload()
    by_id = {s["span_id"]: s for s in spans}
    for s in spans:
        parent_id = s["parent_span_id"]
        if parent_id is None or parent_id not in by_id:
            continue
        parent = by_id[parent_id]
        assert s["start_time"] >= parent["start_time"], (
            f"span {s['name']} starts before parent {parent['name']}"
        )
        assert s["end_time"] <= parent["end_time"], (
            f"span {s['name']} ends after parent {parent['name']}"
        )


# ─── reset clears spans ───────────────────────────────────────────────────────


def test_reset_clears_spans_buffer():
    exporter = _build_exporter_and_emit(
        [{"__name__": "a", "concord.kind": "agent", "concord.agent": "A", "ag2.span.type": "agent"}]
    )
    assert len(exporter.to_spans_payload()) >= 1
    exporter.reset(run_id="new_run", workflow_name="NewWorkflow")
    assert exporter.to_spans_payload() == []


# ─── unrelated spans are skipped ──────────────────────────────────────────────


def test_unrelated_spans_without_concord_attrs_are_dropped():
    """Spans from other instrumentation that share the tracer must not pollute
    the Concord spans payload — only spans with concord.kind / ag2.span.type /
    concord.type are captured."""
    exporter = _build_exporter_and_emit(
        [
            {"__name__": "concord.agent.A", "concord.kind": "agent", "concord.agent": "A", "ag2.span.type": "agent"},
            {"__name__": "unrelated", "http.method": "GET"},  # no concord/ag2 attrs
        ]
    )
    spans = exporter.to_spans_payload()
    # Only synthesized root + 1 concord span
    concord_spans = [s for s in spans if s["kind"] != "workflow"]
    assert len(concord_spans) == 1
    assert concord_spans[0]["agent"] == "A"


# ─── SDK mirror exposes the same API ──────────────────────────────────────────


def test_sdk_mirror_has_to_spans_payload():
    from concord_sdk.trace_adapter import ConcordSpanExporter as SdkExporter

    sdk_exporter = SdkExporter(run_id="sdk_run", workflow_name="Mirror")
    assert hasattr(sdk_exporter, "to_spans_payload")
    assert sdk_exporter.to_spans_payload() == []


# ─── existing zone_a/sdk parity ────────────────────────────────────────────────


def test_zone_a_and_sdk_exporters_produce_identical_payload():
    """The two ConcordSpanExporter copies (zone_a + sdk) must stay in sync.
    Sprint 15 keeps them mirrored via copy; if they drift, this test catches it.
    """
    pytest.importorskip("opentelemetry")
    from zone_a.trace_adapter import ConcordSpanExporter as ZoneAExporter
    from concord_sdk.trace_adapter import ConcordSpanExporter as SdkExporter

    for cls in (ZoneAExporter, SdkExporter):
        exporter = cls(run_id="parity", workflow_name="Parity")
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("concord.test")
        with tracer.start_as_current_span(
            "concord.agent.A",
            attributes={
                "concord.kind": "agent",
                "concord.agent": "A",
                "ag2.span.type": "agent",
            },
        ):
            pass
        provider.force_flush()
        spans = exporter.to_spans_payload()
        # Drop trace_id/span_id which are random per-run
        normalized = [
            {k: v for k, v in s.items() if k not in {"trace_id", "span_id", "parent_span_id", "start_time", "end_time"}}
            for s in spans
        ]
        # Stash for comparison via fixture-style accumulator
        cls._normalized_for_parity = normalized

    assert ZoneAExporter._normalized_for_parity == SdkExporter._normalized_for_parity
