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

# Concord span kinds. Sprint 15 #72 locked the 10-kind contract; the AG2
# OTel namespace maps onto a subset of these. Other kinds (contract_check,
# repair, regression) are stamped by Zone B in #74/#75, not here.
_AG2_KIND_MAP = {
    "agent": "agent",
    "conversation": "agent",
    "tool": "tool",
    "handoff": "handoff",
    "human_input": "human_gate",
    "code_execution": "tool",
    "guardrail": "guardrail",
}
_ALLOWED_SPAN_KINDS = {
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
_CONCORD_SPAN_FIELDS = (
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
)


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


def _hex_span_id(value: Any) -> str | None:
    """Render an OTel span/trace id as a hex string, or None when missing."""
    if value is None:
        return None
    if isinstance(value, int):
        return format(value, "x")
    return str(value)


def _span_kind(attrs: dict[str, Any]) -> str:
    """Concord-native kind for a span. Defaults to 'agent' so unknown spans
    surface in the forensic UI rather than being silently dropped."""
    raw = attrs.get("concord.kind")
    if isinstance(raw, str) and raw in _ALLOWED_SPAN_KINDS:
        return raw
    ag2_type = attrs.get("ag2.span.type")
    if isinstance(ag2_type, str) and ag2_type in _AG2_KIND_MAP:
        return _AG2_KIND_MAP[ag2_type]
    return "agent"


def _span_status(span: Any, attrs: dict[str, Any]) -> str:
    if attrs.get("error.type"):
        return "error"
    status_obj = getattr(span, "status", None)
    if status_obj is None:
        return "ok"
    description = getattr(status_obj, "status_code", None)
    if description is not None and "ERROR" in str(description).upper():
        return "error"
    return "ok"


def _span_error(attrs: dict[str, Any]) -> dict[str, Any] | None:
    error_type = attrs.get("error.type")
    if not error_type:
        return None
    error: dict[str, Any] = {"type": str(error_type)}
    if attrs.get("error.message"):
        error["message"] = str(attrs["error.message"])
    return error


def _span_to_concord_span(span: Any) -> dict[str, Any] | None:
    """Convert one OTel span into Concord's 16-field shape. Returns None for
    spans that don't carry Concord/AG2 attributes (e.g. spans from unrelated
    instrumentation that share the tracer)."""
    attrs = _span_attributes(span)
    if not (
        attrs.get("concord.kind")
        or attrs.get("ag2.span.type")
        or attrs.get("concord.type")
    ):
        return None

    span_context = getattr(span, "context", None)
    trace_id_raw = getattr(span_context, "trace_id", None) if span_context else None
    span_id_raw = getattr(span_context, "span_id", None) if span_context else None
    parent_obj = getattr(span, "parent", None)
    parent_span_id_raw = getattr(parent_obj, "span_id", None) if parent_obj else None

    start_time_ns = getattr(span, "start_time", None)
    end_time_ns = getattr(span, "end_time", None)
    start_time = (start_time_ns / 1_000_000_000) if isinstance(start_time_ns, int) else 0.0
    end_time = (end_time_ns / 1_000_000_000) if isinstance(end_time_ns, int) else start_time
    duration_ms = (
        int((end_time_ns - start_time_ns) / 1_000_000)
        if isinstance(end_time_ns, int) and isinstance(start_time_ns, int)
        else 0
    )

    kind = _span_kind(attrs)
    agent = (
        attrs.get("concord.agent")
        or attrs.get("gen_ai.agent.name")
        or attrs.get("ag2.agent.name")
    )
    tool = attrs.get("gen_ai.tool.name") or attrs.get("concord.tool")

    return {
        "trace_id": _hex_span_id(trace_id_raw) or "",
        "span_id": _hex_span_id(span_id_raw) or "",
        "parent_span_id": _hex_span_id(parent_span_id_raw),
        "name": str(getattr(span, "name", "") or ""),
        "kind": kind,
        "agent": str(agent) if agent else None,
        "tool": str(tool) if tool else None,
        "status": _span_status(span, attrs),
        "start_time": start_time,
        "end_time": end_time,
        "duration_ms": duration_ms,
        "attributes": dict(attrs),
        "input": _safe_json_loads(attrs.get("gen_ai.input.messages")) or {},
        "output": _safe_json_loads(attrs.get("gen_ai.output.messages")) or {},
        "error": _span_error(attrs),
        "contract_refs": [],
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
        self._spans: list[dict[str, Any]] = []
        self._stopped = False

    def export(self, spans: Iterable[Any]) -> SpanExportResult:
        if self._stopped:
            return SpanExportResult.FAILURE
        for span in spans:
            event = _span_to_event(span)
            if event is not None:
                self._events.append(event)
            concord_span = _span_to_concord_span(span)
            if concord_span is not None:
                self._spans.append(concord_span)
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
        self._spans = []
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

    def to_spans_payload(self) -> list[dict[str, Any]]:
        """Concord 16-field spans payload, with a synthesized ``workflow``
        root span wrapping all captured spans. Matches the contract locked
        by Sprint 15 #72 tests (`tests/test_spans_shape.py`).
        """
        if not self._spans:
            return []

        trace_id = self._spans[0]["trace_id"] or ""
        start_time = min(s["start_time"] for s in self._spans)
        end_time = max(s["end_time"] for s in self._spans)
        duration_ms = max(int((end_time - start_time) * 1000), 0)
        root_span_id = f"sp_workflow_{self.run_id}" if self.run_id else "sp_workflow_root"

        root: dict[str, Any] = {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_span_id": None,
            "name": f"concord.workflow.{self.workflow_name}" if self.workflow_name else "concord.workflow",
            "kind": "workflow",
            "agent": None,
            "tool": None,
            "status": "ok",
            "start_time": start_time,
            "end_time": end_time,
            "duration_ms": duration_ms,
            "attributes": {
                "workflow.name": self.workflow_name,
                "run.id": self.run_id,
            },
            "input": {},
            "output": self.final_output if isinstance(self.final_output, dict) else {},
            "error": None,
            "contract_refs": [],
        }

        # Re-parent any span without a parent to the synthesized root so the
        # forensic UI tree always has a single root.
        existing_span_ids = {s["span_id"] for s in self._spans}
        out: list[dict[str, Any]] = [root]
        for span in self._spans:
            copy = dict(span)
            if copy["parent_span_id"] is None or copy["parent_span_id"] not in existing_span_ids:
                copy["parent_span_id"] = root_span_id
            out.append(copy)
        return out

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
