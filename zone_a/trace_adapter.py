from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable
from typing import Any

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


_SUPPORTED_TYPES = {"agent_turn", "tool_call", "handoff", "context_update"}
_UNSET = object()
_AG2_TYPE_MAP = {
    "agent": "agent_turn",
    "conversation": "agent_turn",
    "tool": "tool_call",
    "handoff": "handoff",
    "human_input": "context_update",
    "code_execution": "tool_call",
}


def _json_default(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _loads_mapping(value: Any) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return dict(value)
    parsed = _safe_json_loads(value)
    if isinstance(parsed, dict):
        return parsed
    return {}


def _span_attributes(span: Any) -> dict[str, Any]:
    return dict(getattr(span, "attributes", {}) or {})


def _span_type(attrs: dict[str, Any]) -> str | None:
    raw_type = attrs.get("concord.type")
    if isinstance(raw_type, str) and raw_type in _SUPPORTED_TYPES:
        return raw_type
    ag2_type = attrs.get("ag2.span.type")
    if isinstance(ag2_type, str):
        return _AG2_TYPE_MAP.get(ag2_type)
    return None


def _safe_json_loads(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _span_timestamp(span: Any, attrs: dict[str, Any]) -> float:
    if attrs.get("concord.timestamp") is not None:
        return float(attrs["concord.timestamp"])
    start_time = getattr(span, "start_time", None)
    if isinstance(start_time, int):
        return start_time / 1_000_000_000
    return 0.0


def _content_from_messages(raw_messages: Any) -> str:
    messages = _safe_json_loads(raw_messages)
    if not isinstance(messages, list):
        return ""
    chunks: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        for part in message.get("parts", []):
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and part.get("content"):
                chunks.append(str(part["content"]))
            elif part.get("type") == "tool_call" and part.get("name"):
                chunks.append(f"tool_call:{part['name']}")
            elif part.get("type") == "tool_call_response" and part.get("response"):
                chunks.append(str(part["response"]))
    return " ".join(chunks)


def _native_content(span: Any, attrs: dict[str, Any], event_type: str) -> str:
    if event_type == "tool_call":
        tool_name = attrs.get("gen_ai.tool.name") or "tool"
        result = attrs.get("gen_ai.tool.call.result")
        if result is not None:
            return f"{tool_name}: {result}"
        args = attrs.get("gen_ai.tool.call.arguments")
        return f"{tool_name}: {args}" if args is not None else str(tool_name)
    output = _content_from_messages(attrs.get("gen_ai.output.messages"))
    if output:
        return output
    human_response = attrs.get("ag2.human_input.response")
    if human_response is not None:
        return str(human_response)
    return str(getattr(span, "name", ""))


def _native_context_delta(attrs: dict[str, Any], event_type: str, timestamp: float) -> dict[str, Any]:
    if event_type == "tool_call":
        call_id = str(attrs.get("gen_ai.tool.call.id") or "")
        return {
            "tool_events": [
                {
                    "tool_name": str(attrs.get("gen_ai.tool.name") or "tool"),
                    "input": attrs.get("gen_ai.tool.call.arguments") or "",
                    "output": attrs.get("gen_ai.tool.call.result") or "",
                    "status": "failure" if attrs.get("error.type") else "success",
                    "evidence_id": call_id,
                    "timestamp": timestamp,
                }
            ]
        }
    if event_type == "context_update" and attrs.get("ag2.human_input.response") is not None:
        return {"human_input": attrs["ag2.human_input.response"]}
    return {}


def _span_to_event(span: Any) -> dict[str, Any] | None:
    attrs = _span_attributes(span)
    event_type = _span_type(attrs)
    if event_type is None:
        return None
    agent = (
        attrs.get("concord.agent")
        or attrs.get("gen_ai.agent.name")
        or attrs.get("ag2.agent.name")
        or attrs.get("gen_ai.tool.name")
    )
    if agent is None:
        return None

    timestamp = _span_timestamp(span, attrs)
    step = attrs.get("concord.step") or attrs.get("ag2.step")
    context_delta = _loads_mapping(attrs.get("concord.context_delta"))
    if not context_delta:
        context_delta = _native_context_delta(attrs, event_type, timestamp)
    handoff_to = attrs.get("concord.handoff_to")
    tool_call_id = attrs.get("concord.tool_call_id") or attrs.get("gen_ai.tool.call.id")
    return {
        "step": int(step) if step is not None else None,
        "agent": str(agent),
        "type": event_type,
        "content": str(attrs.get("concord.content") or _native_content(span, attrs, event_type)),
        "tool_call_id": tool_call_id,
        "context_delta": context_delta,
        "handoff_to": str(handoff_to) if handoff_to else None,
        "timestamp": timestamp,
    }


class ConcordSpanExporter(SpanExporter):
    def __init__(
        self,
        *,
        run_id: str = "",
        workflow_name: str = "",
        final_output: Any = None,
    ) -> None:
        self.run_id = run_id
        self.workflow_name = workflow_name
        self.final_output = final_output
        self._events: list[dict[str, Any]] = []
        self._stopped = False

    def export(self, spans: Iterable[Any]) -> SpanExportResult:
        if self._stopped:
            return SpanExportResult.FAILURE
        for span in spans:
            event = _span_to_event(span)
            if event is not None:
                self._events.append(event)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self._stopped = True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def reset(
        self,
        *,
        run_id: str = "",
        workflow_name: str = "",
        final_output: Any = None,
    ) -> None:
        self.run_id = run_id
        self.workflow_name = workflow_name
        self.final_output = final_output
        self._events = []
        self._stopped = False

    def configure(
        self,
        *,
        run_id: str | None = None,
        workflow_name: str | None = None,
        final_output: Any = _UNSET,
    ) -> None:
        if run_id is not None:
            self.run_id = run_id
        if workflow_name is not None:
            self.workflow_name = workflow_name
        if final_output is not _UNSET:
            self.final_output = final_output

    def to_run_trace_dict(self) -> dict[str, Any]:
        events = sorted(
            enumerate(self._events),
            key=lambda item: (
                item[1]["step"] is None,
                item[1]["step"] if item[1]["step"] is not None else item[1]["timestamp"],
                item[0],
            ),
        )
        normalized: list[dict[str, Any]] = []
        for index, (_, event) in enumerate(events):
            copied = dict(event)
            if copied["step"] is None:
                copied["step"] = index + 1
            if copied["handoff_to"] is None and index + 1 < len(events):
                copied["handoff_to"] = events[index + 1][1]["agent"]
            normalized.append(copied)
        return {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "events": normalized,
            "final_output": self.final_output,
        }


def emit_trace_spans(tracer: Any, raw_trace: dict[str, Any]) -> None:
    for event in raw_trace.get("events", []):
        attrs: dict[str, Any] = {
            "concord.type": event["type"],
            "concord.step": event["step"],
            "concord.agent": event["agent"],
            "concord.content": event.get("content") or "",
            "concord.context_delta": json.dumps(
                event.get("context_delta") or {},
                default=_json_default,
            ),
            "concord.timestamp": event.get("timestamp", 0.0),
        }
        if event.get("tool_call_id") is not None:
            attrs["concord.tool_call_id"] = event["tool_call_id"]
        if event.get("handoff_to") is not None:
            attrs["concord.handoff_to"] = event["handoff_to"]

        with tracer.start_as_current_span(
            f"concord.{event['type']}.{event['agent']}",
            attributes=attrs,
        ):
            pass
