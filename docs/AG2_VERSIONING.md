# AG2 Versioning Notes

Verified locally on 2026-05-07:

- `ag2==0.12.2`
- `opentelemetry-api==1.41.1`
- `opentelemetry-sdk==1.41.1`
- `opentelemetry-exporter-otlp-proto-http==1.41.1`

## Working Imports

```python
from autogen.opentelemetry import instrument_agent
from autogen.opentelemetry import instrument_llm_wrapper
from autogen.opentelemetry import instrument_pattern
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
```

## Verified Signatures

```text
instrument_agent(agent, *, tracer_provider: TracerProvider) -> Agent
instrument_llm_wrapper(*, tracer_provider: TracerProvider, capture_messages: bool = False) -> None
instrument_pattern(pattern, *, tracer_provider: TracerProvider) -> Pattern
```

The gRPC OTLP exporter path shown in some installed AG2 examples is not
available in this environment. Use the HTTP OTLP exporter or local exporters
above.

## Concord Mapping

AG2 emits tracing span types such as `conversation`, `agent`, `tool`,
`speaker_selection`, `human_input`, and `code_execution` through
`ag2.span.type`. Concord's internal trace model uses `agent_turn`, `tool_call`,
`handoff`, and `context_update`.

The Sprint 6 adapter maps native `agent` to `agent_turn` and native `tool` to
`tool_call` when the Concord attributes are present. `handoff` and
`context_update` are synthesized by Concord instrumentation because the
installed AG2 tracing package does not emit those as complete first-class
workflow events.

## Spike

Run the local spike from the repository root:

```bash
python3 scripts/otel_spike.py
```

The script instruments the Zone A swarm agents with the verified AG2 import
paths, executes one instrumented tool call through an agent method, and prints
both the native span attributes and the normalized Concord trace event.
