from __future__ import annotations

import json

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


def test_trace_spans_round_trip_to_canonical_run_trace(clean_trace_raw):
    from zone_a.trace_adapter import ConcordSpanExporter, emit_trace_spans

    exporter = ConcordSpanExporter(
        run_id=clean_trace_raw["run_id"],
        workflow_name=clean_trace_raw["workflow_name"],
        final_output=clean_trace_raw["final_output"],
    )
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    emit_trace_spans(provider.get_tracer("concord.test"), clean_trace_raw)
    provider.force_flush()

    assert json.dumps(exporter.to_run_trace_dict(), indent=2) == json.dumps(
        clean_trace_raw,
        indent=2,
    )


def test_exporter_derives_handoff_when_span_does_not_include_it():
    from zone_a.trace_adapter import ConcordSpanExporter

    exporter = ConcordSpanExporter(run_id="run_handoff", workflow_name="Workflow")
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("concord.test")

    with tracer.start_as_current_span(
        "agent.a",
        attributes={
            "concord.type": "agent_turn",
            "concord.step": 1,
            "concord.agent": "ResearcherAgent",
            "concord.content": "found sources",
            "concord.context_delta": "{}",
        },
    ):
        pass
    with tracer.start_as_current_span(
        "agent.b",
        attributes={
            "concord.type": "agent_turn",
            "concord.step": 2,
            "concord.agent": "CriticAgent",
            "concord.content": "critiqued sources",
            "concord.context_delta": "{}",
        },
    ):
        pass

    events = exporter.to_run_trace_dict()["events"]

    assert events[0]["handoff_to"] == "CriticAgent"
    assert events[1]["handoff_to"] is None


def test_exporter_preserves_tool_call_and_context_update_spans():
    from zone_a.trace_adapter import ConcordSpanExporter

    exporter = ConcordSpanExporter(run_id="run_tools", workflow_name="Workflow")
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("concord.test")

    with tracer.start_as_current_span(
        "tool.search",
        attributes={
            "concord.type": "tool_call",
            "concord.step": 1,
            "concord.agent": "ResearcherAgent",
            "concord.content": "search executed",
            "concord.tool_call_id": "tc_001",
            "concord.context_delta": json.dumps(
                {
                    "tool_events": [
                        {
                            "tool_name": "tavily_search",
                            "input": "q",
                            "output": "r",
                            "status": "success",
                            "evidence_id": "ev_001",
                            "timestamp": 0.1,
                        }
                    ]
                }
            ),
        },
    ):
        pass
    with tracer.start_as_current_span(
        "context.update",
        attributes={
            "concord.type": "context_update",
            "concord.step": 2,
            "concord.agent": "VerifierAgent",
            "concord.content": "context updated",
            "concord.context_delta": '{"verified_sources_count": 3}',
        },
    ):
        pass

    events = exporter.to_run_trace_dict()["events"]

    assert events[0]["type"] == "tool_call"
    assert events[0]["tool_call_id"] == "tc_001"
    assert events[0]["context_delta"]["tool_events"][0]["evidence_id"] == "ev_001"
    assert events[1]["type"] == "context_update"
    assert events[1]["context_delta"] == {"verified_sources_count": 3}


def test_exporter_maps_native_ag2_agent_and_tool_spans():
    from zone_a.trace_adapter import ConcordSpanExporter

    exporter = ConcordSpanExporter(run_id="run_native", workflow_name="Workflow")
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("concord.test")

    with tracer.start_as_current_span(
        "invoke_agent VerifierAgent",
        attributes={
            "ag2.span.type": "agent",
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "VerifierAgent",
            "gen_ai.output.messages": json.dumps(
                [
                    {
                        "role": "assistant",
                        "parts": [{"type": "text", "content": "Verified claims."}],
                    }
                ]
            ),
        },
    ):
        pass
    with tracer.start_as_current_span(
        "execute_tool tavily_search",
        attributes={
            "ag2.span.type": "tool",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "tavily_search",
            "gen_ai.tool.call.id": "tc_native",
            "gen_ai.tool.call.arguments": '{"query": "reliability"}',
            "gen_ai.tool.call.result": "3 results",
        },
    ):
        pass

    events = exporter.to_run_trace_dict()["events"]

    assert events[0]["step"] == 1
    assert events[0]["agent"] == "VerifierAgent"
    assert events[0]["type"] == "agent_turn"
    assert events[0]["content"] == "Verified claims."
    assert events[1]["step"] == 2
    assert events[1]["agent"] == "tavily_search"
    assert events[1]["type"] == "tool_call"
    assert events[1]["tool_call_id"] == "tc_native"
    assert events[1]["context_delta"]["tool_events"][0]["status"] == "success"


def test_exporter_ignores_unknown_ag2_spans_without_losing_known_spans():
    from zone_a.trace_adapter import ConcordSpanExporter

    exporter = ConcordSpanExporter(run_id="run_partial", workflow_name="Workflow")
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("concord.test")

    with tracer.start_as_current_span(
        "ag2.speaker_selection",
        attributes={
            "ag2.span.type": "speaker_selection",
            "concord.step": 1,
            "concord.agent": "ResearcherAgent",
        },
    ):
        pass
    with tracer.start_as_current_span(
        "concord.agent",
        attributes={
            "concord.type": "agent_turn",
            "concord.step": 2,
            "concord.agent": "VerifierAgent",
            "concord.content": "stopped",
            "concord.context_delta": '{"verified_sources_count": 0}',
        },
    ):
        pass

    events = exporter.to_run_trace_dict()["events"]

    assert [event["agent"] for event in events] == ["VerifierAgent"]
    assert events[0]["context_delta"] == {"verified_sources_count": 0}


def test_exporter_sorts_out_of_order_spans_and_skips_malformed_events():
    from zone_a.trace_adapter import ConcordSpanExporter

    exporter = ConcordSpanExporter(run_id="run_order", workflow_name="Workflow")
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("concord.test")

    with tracer.start_as_current_span(
        "late.agent",
        attributes={
            "concord.type": "agent_turn",
            "concord.step": 3,
            "concord.agent": "VerifierAgent",
            "concord.content": "verified",
            "concord.context_delta": "{}",
        },
    ):
        pass
    with tracer.start_as_current_span(
        "malformed.agent",
        attributes={
            "concord.type": "agent_turn",
            "concord.step": 2,
            "concord.content": "missing agent",
            "concord.context_delta": "{}",
        },
    ):
        pass
    with tracer.start_as_current_span(
        "early.agent",
        attributes={
            "concord.type": "agent_turn",
            "concord.step": 1,
            "concord.agent": "ResearcherAgent",
            "concord.content": "researched",
            "concord.context_delta": "{}",
        },
    ):
        pass

    events = exporter.to_run_trace_dict()["events"]

    assert [event["step"] for event in events] == [1, 3]
    assert events[0]["handoff_to"] == "VerifierAgent"


def test_exporter_treats_malformed_context_delta_as_empty_mapping():
    from zone_a.trace_adapter import ConcordSpanExporter

    exporter = ConcordSpanExporter(run_id="run_bad_context", workflow_name="Workflow")
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("concord.test")

    with tracer.start_as_current_span(
        "bad.context",
        attributes={
            "concord.type": "agent_turn",
            "concord.step": 1,
            "concord.agent": "VerifierAgent",
            "concord.content": "bad context",
            "concord.context_delta": "{not-json",
        },
    ):
        pass

    events = exporter.to_run_trace_dict()["events"]

    assert events[0]["agent"] == "VerifierAgent"
    assert events[0]["context_delta"] == {}
