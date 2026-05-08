from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from autogen.opentelemetry import instrument_agent, instrument_llm_wrapper, instrument_pattern
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from concord_sdk.client import ConcordClient
from concord_sdk.trace_adapter import ConcordSpanExporter, emit_trace_spans


def _agent_name(agent: Any) -> str:
    return str(getattr(agent, "name", agent.__class__.__name__))


def _as_agent_list(workflow_agents: Any) -> list[Any]:
    if workflow_agents is None:
        return []
    if isinstance(workflow_agents, Iterable) and not isinstance(workflow_agents, (str, bytes)):
        return list(workflow_agents)
    return []


def _default_workflow_definition(workflow_agents: list[Any], workflow_name: str) -> dict[str, Any]:
    agents = [{"name": _agent_name(agent)} for agent in workflow_agents]
    return {
        "name": workflow_name,
        "owner": "sdk",
        "declared_topology": {"entry": agents[0]["name"] if agents else "", "edges": []},
        "agents": agents,
        "tools": [],
        "contracts": [],
    }


@dataclass
class ConcordInstrumentation:
    client: ConcordClient
    workflow_id: str
    tracer_provider: TracerProvider
    exporter: ConcordSpanExporter
    instrumented_agents: list[Any] = field(default_factory=list)
    last_run_id: str = ""

    def complete(self, raw_trace: dict[str, Any] | None = None) -> dict[str, str]:
        raw_trace = raw_trace or {}
        self.exporter.configure(
            run_id=str(raw_trace.get("run_id") or self.exporter.run_id),
            workflow_name=str(raw_trace.get("workflow_name") or self.exporter.workflow_name),
            final_output=raw_trace.get("final_output"),
        )
        self.tracer_provider.force_flush()
        normalized = self.exporter.to_run_trace_dict()
        if not normalized["events"] and raw_trace.get("events"):
            self.exporter.reset(
                run_id=str(raw_trace.get("run_id") or ""),
                workflow_name=str(raw_trace.get("workflow_name") or ""),
                final_output=raw_trace.get("final_output"),
            )
            emit_trace_spans(self.tracer_provider.get_tracer("concord.sdk"), raw_trace)
            self.tracer_provider.force_flush()
            normalized = self.exporter.to_run_trace_dict()
        submitted = self.client.submit_run(
            self.workflow_id,
            normalized,
        )
        self.exporter.reset(
            run_id=self.exporter.run_id,
            workflow_name=self.exporter.workflow_name,
            final_output=self.exporter.final_output,
        )
        self.last_run_id = submitted["run_id"]
        return submitted


def instrument(
    workflow_agents: Any,
    api_url: str,
    api_key: str,
    *,
    tenant_id: str = "local",
    workflow_id: str = "",
    workflow_name: str = "InstrumentedWorkflow",
    workflow_definition: dict[str, Any] | None = None,
    client: ConcordClient | None = None,
    tracer_provider: TracerProvider | None = None,
    run_trace: dict[str, Any] | None = None,
) -> ConcordInstrumentation:
    provider = tracer_provider or TracerProvider()
    exporter = ConcordSpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    client = client or ConcordClient(api_url, api_key=api_key, tenant_id=tenant_id)

    agent_list = _as_agent_list(workflow_agents)
    instrumented_agents = [
        instrument_agent(agent, tracer_provider=provider)
        for agent in agent_list
    ]
    if (
        not agent_list
        and workflow_agents is not None
        and not isinstance(workflow_agents, Iterable)
    ):
        instrument_pattern(workflow_agents, tracer_provider=provider)
    instrument_llm_wrapper(tracer_provider=provider, capture_messages=False)

    if not workflow_id:
        definition = workflow_definition or _default_workflow_definition(
            agent_list,
            workflow_name,
        )
        workflow_id = client.register_workflow(definition)["workflow_id"]

    session = ConcordInstrumentation(
        client=client,
        workflow_id=workflow_id,
        tracer_provider=provider,
        exporter=exporter,
        instrumented_agents=instrumented_agents,
    )
    if run_trace is not None:
        session.complete(run_trace)
    return session
