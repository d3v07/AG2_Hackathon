#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autogen.opentelemetry import instrument_agent, instrument_llm_wrapper
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from zone_a.swarm import build_swarm
from zone_a.trace_adapter import ConcordSpanExporter


def main() -> int:
    provider = TracerProvider()
    memory_exporter = InMemorySpanExporter()
    concord_exporter = ConcordSpanExporter(
        run_id="otel_spike",
        workflow_name="LiteratureReviewAssistant",
    )
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    provider.add_span_processor(SimpleSpanProcessor(concord_exporter))

    agents, _ = build_swarm(llm_config={"config_list": [{"model": "test", "api_key": "x"}]})
    for agent in agents:
        instrument_agent(agent, tracer_provider=provider)
    instrument_llm_wrapper(tracer_provider=provider, capture_messages=False)

    def spike_tool() -> str:
        return "ok"

    agents[0].register_for_execution(name="spike_tool")(spike_tool)
    agents[0].execute_function(
        {
            "name": "spike_tool",
            "arguments": "{}",
        },
        call_id="tc_spike",
        verbose=False,
    )

    provider.force_flush()
    for span in memory_exporter.get_finished_spans():
        print(f"{span.name} {dict(span.attributes)}")
    normalized = concord_exporter.to_run_trace_dict()
    print(normalized)
    return 0 if memory_exporter.get_finished_spans() and normalized["events"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
