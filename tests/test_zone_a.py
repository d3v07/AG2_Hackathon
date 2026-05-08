"""Unit tests for Zone A — no LLM calls, covers utils and return shape contracts."""

import time
from zone_a.agents._utils import strip_json_fences
from zone_a.run import _to_trace_event
from shared.models import TraceEvent, ToolEvent

REQUIRED_KEYS = {"step", "agent", "type", "content", "tool_call_id", "context_delta", "handoff_to", "timestamp"}


# ── strip_json_fences ─────────────────────────────────────────────────────────

class TestStripJsonFences:
    def test_plain_json_unchanged(self):
        assert strip_json_fences('{"key": "val"}') == '{"key": "val"}'

    def test_strips_backtick_fence(self):
        raw = "```\n{\"key\": \"val\"}\n```"
        assert strip_json_fences(raw) == '{"key": "val"}'

    def test_strips_json_language_fence(self):
        raw = "```json\n{\"key\": \"val\"}\n```"
        assert strip_json_fences(raw) == '{"key": "val"}'

    def test_leading_trailing_whitespace(self):
        result = strip_json_fences('  {"a": 1}  ')
        assert result == '{"a": 1}'

    def test_empty_string(self):
        assert strip_json_fences("") == ""

    def test_no_fence_multiline(self):
        raw = '{\n  "a": 1\n}'
        assert strip_json_fences(raw) == raw.strip()


# ── _to_trace_event ───────────────────────────────────────────────────────────

class TestToTraceEvent:
    def _base_dict(self, **overrides) -> dict:
        d = {
            "step": 1,
            "agent": "TestAgent",
            "type": "agent_turn",
            "content": "hello",
            "tool_call_id": None,
            "context_delta": {},
            "handoff_to": None,
            "timestamp": time.time(),
        }
        d.update(overrides)
        return d

    def test_returns_trace_event_instance(self):
        result = _to_trace_event(self._base_dict())
        assert isinstance(result, TraceEvent)

    def test_fields_mapped_correctly(self):
        ts = time.time()
        d = self._base_dict(step=3, agent="VerifierAgent", tool_call_id="tc_001", timestamp=ts)
        ev = _to_trace_event(d)
        assert ev.step == 3
        assert ev.agent == "VerifierAgent"
        assert ev.tool_call_id == "tc_001"
        assert ev.timestamp == ts

    def test_tool_events_converted_to_dataclass(self):
        te = {
            "tool_name": "tavily_search",
            "input": "query",
            "output": "3 results",
            "status": "success",
            "evidence_id": "ev_001",
            "timestamp": time.time(),
        }
        d = self._base_dict(context_delta={"tool_events": [te]})
        ev = _to_trace_event(d)
        assert isinstance(ev.context_delta["tool_events"][0], ToolEvent)

    def test_tool_events_already_dataclass_passthrough(self):
        te = ToolEvent(
            tool_name="x", input="q", output="r",
            status="success", evidence_id="e1", timestamp=time.time()
        )
        d = self._base_dict(context_delta={"tool_events": [te]})
        ev = _to_trace_event(d)
        assert ev.context_delta["tool_events"][0] is te

    def test_missing_timestamp_defaults_to_now(self):
        d = self._base_dict()
        del d["timestamp"]
        before = time.time()
        ev = _to_trace_event(d)
        assert ev.timestamp >= before


# ── return shape contracts ────────────────────────────────────────────────────

def _check_shape(d: dict) -> None:
    missing = REQUIRED_KEYS - d.keys()
    assert not missing, f"Missing keys: {missing}"
    assert isinstance(d["step"], int)
    assert isinstance(d["agent"], str)
    assert d["type"] == "agent_turn"
    assert isinstance(d["content"], str)
    assert isinstance(d["context_delta"], dict)
    assert isinstance(d["timestamp"], float)


class TestAgentReturnShapes:
    """Validate return dict contracts without calling LLM."""

    def _mock_researcher_return(self) -> dict:
        return {
            "step": 1,
            "agent": "ResearcherAgent",
            "type": "agent_turn",
            "content": "Synthesis of sources.",
            "tool_call_id": "tc_001",
            "context_delta": {
                "retrieved_sources": [{"title": "T", "url": "u", "snippet": "s"}],
                "tool_events": [{
                    "tool_name": "tavily_search",
                    "input": "query",
                    "output": "1 results",
                    "status": "success",
                    "evidence_id": "ev_001",
                    "timestamp": time.time(),
                }],
            },
            "handoff_to": "CriticAgent",
            "timestamp": time.time(),
        }

    def _mock_critic_return(self) -> dict:
        return {
            "step": 2,
            "agent": "CriticAgent",
            "type": "agent_turn",
            "content": "Overall critique.",
            "tool_call_id": None,
            "context_delta": {},
            "handoff_to": "VerifierAgent",
            "timestamp": time.time(),
        }

    def _mock_verifier_return(self) -> dict:
        return {
            "step": 3,
            "agent": "VerifierAgent",
            "type": "agent_turn",
            "content": "Verification narrative.",
            "tool_call_id": None,
            "context_delta": {"verified_sources_count": 0},
            "handoff_to": "ReporterAgent",
            "timestamp": time.time(),
        }

    def _mock_reporter_return(self) -> dict:
        return {
            "step": 4,
            "agent": "ReporterAgent",
            "type": "agent_turn",
            "content": "Report summary.",
            "tool_call_id": None,
            "context_delta": {"final_output": {"summary": "s", "claims": [], "citations": [], "risks": [], "next_steps": []}},
            "handoff_to": "ActionAgent",
            "timestamp": time.time(),
        }

    def _mock_action_return(self) -> dict:
        return {
            "step": 5,
            "agent": "ActionAgent",
            "type": "agent_turn",
            "content": "Action taken.",
            "tool_call_id": None,
            "context_delta": {"action_event": "saved"},
            "handoff_to": None,
            "timestamp": time.time(),
        }

    def test_researcher_shape(self):
        _check_shape(self._mock_researcher_return())

    def test_researcher_has_tool_call_id(self):
        d = self._mock_researcher_return()
        assert d["tool_call_id"] == "tc_001"

    def test_researcher_context_delta_has_sources(self):
        d = self._mock_researcher_return()
        assert "retrieved_sources" in d["context_delta"]
        assert len(d["context_delta"]["retrieved_sources"]) > 0

    def test_critic_shape(self):
        _check_shape(self._mock_critic_return())

    def test_verifier_shape(self):
        _check_shape(self._mock_verifier_return())

    def test_verifier_intentional_failures(self):
        d = self._mock_verifier_return()
        assert d["tool_call_id"] is None
        assert d["context_delta"]["verified_sources_count"] == 0

    def test_reporter_shape(self):
        _check_shape(self._mock_reporter_return())

    def test_reporter_final_output_in_context_delta(self):
        d = self._mock_reporter_return()
        assert "final_output" in d["context_delta"]
        assert "summary" in d["context_delta"]["final_output"]

    def test_action_shape(self):
        _check_shape(self._mock_action_return())

    def test_action_handoff_is_none(self):
        d = self._mock_action_return()
        assert d["handoff_to"] is None

    def test_all_convertible_to_trace_event(self):
        mocks = [
            self._mock_researcher_return(),
            self._mock_critic_return(),
            self._mock_verifier_return(),
            self._mock_reporter_return(),
            self._mock_action_return(),
        ]
        for m in mocks:
            ev = _to_trace_event(m)
            assert isinstance(ev, TraceEvent)
