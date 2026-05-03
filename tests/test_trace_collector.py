"""Tests for zone_b/agents/trace_collector.py"""
import asyncio
import pytest
from shared.models import RunTrace, TraceEvent, ToolEvent, ContextSnapshot
from zone_b.agents.trace_collector import (
    run_trace_collector, _parse_tool_events,
    _parse_trace_events, _build_context_snapshot,
)


# ---------------------------------------------------------------------------
# _parse_tool_events
# ---------------------------------------------------------------------------

class TestParseToolEvents:
    def test_parses_single_event(self):
        raw = [{"tool_name": "tavily_search", "input": "q", "output": "r",
                "status": "success", "evidence_id": "ev_001", "timestamp": 0.5}]
        result = _parse_tool_events(raw)
        assert len(result) == 1
        assert isinstance(result[0], ToolEvent)
        assert result[0].tool_name == "tavily_search"
        assert result[0].evidence_id == "ev_001"

    def test_parses_multiple_events(self):
        raw = [
            {"tool_name": "tavily_search", "input": "q1", "output": "r1",
             "status": "success", "evidence_id": "ev_001", "timestamp": 0.1},
            {"tool_name": "daytona_run", "input": "code", "output": "ok",
             "status": "success", "evidence_id": "ev_002", "timestamp": 0.2},
        ]
        result = _parse_tool_events(raw)
        assert len(result) == 2
        assert result[1].tool_name == "daytona_run"

    def test_empty_list(self):
        assert _parse_tool_events([]) == []

    def test_missing_optional_fields_use_defaults(self):
        raw = [{}]
        result = _parse_tool_events(raw)
        assert result[0].tool_name == ""
        assert result[0].status == "success"
        assert result[0].timestamp == 0.0
        assert result[0].evidence_id == ""

    def test_failure_status_preserved(self):
        raw = [{"tool_name": "t", "input": None, "output": None,
                "status": "failure", "evidence_id": "", "timestamp": 0.0}]
        assert _parse_tool_events(raw)[0].status == "failure"


# ---------------------------------------------------------------------------
# _parse_trace_events
# ---------------------------------------------------------------------------

class TestParseTraceEvents:
    def test_parses_basic_event(self):
        raw = [{
            "step": 1, "agent": "ResearcherAgent", "type": "agent_turn",
            "content": "Found sources", "tool_call_id": "tc_001",
            "context_delta": {}, "handoff_to": "CriticAgent", "timestamp": 0.5
        }]
        result = _parse_trace_events(raw)
        assert len(result) == 1
        assert isinstance(result[0], TraceEvent)
        assert result[0].agent == "ResearcherAgent"
        assert result[0].tool_call_id == "tc_001"

    def test_null_tool_call_id(self):
        raw = [{"step": 3, "agent": "VerifierAgent", "type": "agent_turn",
                "content": "Done", "tool_call_id": None,
                "context_delta": {}, "handoff_to": None, "timestamp": 1.0}]
        result = _parse_trace_events(raw)
        assert result[0].tool_call_id is None

    def test_normalises_tool_events_in_context_delta(self):
        raw = [{
            "step": 1, "agent": "ResearcherAgent", "type": "agent_turn",
            "content": "Found", "tool_call_id": "tc_001",
            "context_delta": {
                "tool_events": [
                    {"tool_name": "tavily_search", "input": "q", "output": "r",
                     "status": "success", "evidence_id": "ev_1", "timestamp": 0.1}
                ]
            },
            "handoff_to": "CriticAgent", "timestamp": 0.1
        }]
        result = _parse_trace_events(raw)
        tool_events = result[0].context_delta["tool_events"]
        assert len(tool_events) == 1
        assert isinstance(tool_events[0], ToolEvent)

    def test_non_list_tool_events_left_as_is(self):
        raw = [{
            "step": 1, "agent": "A", "type": "agent_turn", "content": "",
            "tool_call_id": None,
            "context_delta": {"tool_events": "not_a_list"},
            "handoff_to": None, "timestamp": 0.0
        }]
        result = _parse_trace_events(raw)
        assert result[0].context_delta["tool_events"] == "not_a_list"

    def test_empty_events(self):
        assert _parse_trace_events([]) == []

    def test_missing_optional_fields_default(self):
        raw = [{"step": 1, "agent": "A", "type": "agent_turn", "content": ""}]
        result = _parse_trace_events(raw)
        assert result[0].tool_call_id is None
        assert result[0].handoff_to is None
        assert result[0].timestamp == 0.0
        assert result[0].context_delta == {}

    def test_preserves_event_order(self):
        raw = [
            {"step": 1, "agent": "A", "type": "t", "content": "",
             "tool_call_id": None, "context_delta": {}, "handoff_to": "B", "timestamp": 0.1},
            {"step": 2, "agent": "B", "type": "t", "content": "",
             "tool_call_id": None, "context_delta": {}, "handoff_to": None, "timestamp": 0.2},
        ]
        result = _parse_trace_events(raw)
        assert result[0].agent == "A"
        assert result[1].agent == "B"


# ---------------------------------------------------------------------------
# _build_context_snapshot
# ---------------------------------------------------------------------------

class TestBuildContextSnapshot:
    def _make_event(self, delta: dict) -> TraceEvent:
        return TraceEvent(step=1, agent="A", type="agent_turn", content="",
                          tool_call_id=None, context_delta=delta,
                          handoff_to=None, timestamp=0.0)

    def test_defaults_when_no_deltas(self):
        snap = _build_context_snapshot([])
        assert snap.verified_sources_count == 0
        assert snap.approval_status == "pending"
        assert snap.retrieved_sources == []
        assert snap.tool_events == []
        assert snap.failed_agent is None

    def test_folds_verified_sources_count(self):
        events = [
            self._make_event({"verified_sources_count": 2}),
            self._make_event({"verified_sources_count": 0}),
        ]
        snap = _build_context_snapshot(events)
        assert snap.verified_sources_count == 0

    def test_last_write_wins_for_scalar(self):
        events = [
            self._make_event({"approval_status": "approved"}),
            self._make_event({"approval_status": "pending"}),
        ]
        snap = _build_context_snapshot(events)
        assert snap.approval_status == "pending"

    def test_tool_events_accumulate(self):
        te1 = ToolEvent(tool_name="t1", input=None, output=None,
                        status="success", evidence_id="e1", timestamp=0.1)
        te2 = ToolEvent(tool_name="t2", input=None, output=None,
                        status="success", evidence_id="e2", timestamp=0.2)
        events = [
            self._make_event({"tool_events": [te1]}),
            self._make_event({"tool_events": [te2]}),
        ]
        snap = _build_context_snapshot(events)
        assert len(snap.tool_events) == 2

    def test_retrieved_sources_overwritten(self):
        events = [
            self._make_event({"retrieved_sources": ["s1", "s2"]}),
            self._make_event({"retrieved_sources": ["s3"]}),
        ]
        snap = _build_context_snapshot(events)
        assert snap.retrieved_sources == ["s3"]

    def test_final_output_set(self):
        events = [self._make_event({"final_output": {"summary": "done"}})]
        snap = _build_context_snapshot(events)
        assert snap.final_output == {"summary": "done"}

    def test_unknown_keys_ignored(self):
        events = [self._make_event({"unknown_key": "value"})]
        snap = _build_context_snapshot(events)
        assert isinstance(snap, ContextSnapshot)


# ---------------------------------------------------------------------------
# run_trace_collector (integration — uses sample_trace.json)
# ---------------------------------------------------------------------------

class TestRunTraceCollector:
    def test_returns_correct_keys(self, sample_trace_raw):
        result = asyncio.run(run_trace_collector(sample_trace_raw))
        assert set(result.keys()) == {"run_trace", "context_snapshot",
                                       "handoff_path", "tool_events", "summary"}

    def test_run_trace_shape(self, sample_trace_raw):
        result = asyncio.run(run_trace_collector(sample_trace_raw))
        rt = result["run_trace"]
        assert isinstance(rt, RunTrace)
        assert rt.run_id == "run_041"
        assert rt.workflow_name == "LiteratureReviewAssistant"
        assert len(rt.events) == 5

    def test_all_events_are_trace_events(self, sample_trace_raw):
        result = asyncio.run(run_trace_collector(sample_trace_raw))
        for e in result["run_trace"].events:
            assert isinstance(e, TraceEvent)

    def test_context_snapshot_shape(self, sample_trace_raw):
        result = asyncio.run(run_trace_collector(sample_trace_raw))
        snap = result["context_snapshot"]
        assert isinstance(snap, ContextSnapshot)
        assert snap.verified_sources_count == 0
        assert snap.approval_status == "pending"

    def test_handoff_path_order(self, sample_trace_raw):
        result = asyncio.run(run_trace_collector(sample_trace_raw))
        assert result["handoff_path"] == [
            "ResearcherAgent", "CriticAgent", "VerifierAgent",
            "ReporterAgent", "ActionAgent"
        ]

    def test_tool_events_extracted(self, sample_trace_raw):
        result = asyncio.run(run_trace_collector(sample_trace_raw))
        assert len(result["tool_events"]) == 1
        assert result["tool_events"][0].tool_name == "tavily_search"

    def test_summary_format(self, sample_trace_raw):
        result = asyncio.run(run_trace_collector(sample_trace_raw))
        summary = result["summary"]
        assert "run_041" in summary
        assert "5 events" in summary
        assert "1 tool call" in summary

    def test_clean_trace_no_violations_snapshot(self, clean_trace_raw):
        result = asyncio.run(run_trace_collector(clean_trace_raw))
        snap = result["context_snapshot"]
        assert snap.verified_sources_count == 3
        assert snap.approval_status == "approved"

    def test_empty_events(self):
        raw = {"run_id": "r", "workflow_name": "w", "events": [], "final_output": None}
        result = asyncio.run(run_trace_collector(raw))
        assert result["handoff_path"] == []
        assert result["tool_events"] == []
        assert result["run_trace"].events == []

    def test_verifier_tool_call_id_is_none(self, sample_trace_raw):
        result = asyncio.run(run_trace_collector(sample_trace_raw))
        verifier = next(e for e in result["run_trace"].events if e.agent == "VerifierAgent")
        assert verifier.tool_call_id is None

    def test_researcher_tool_call_id_present(self, sample_trace_raw):
        result = asyncio.run(run_trace_collector(sample_trace_raw))
        researcher = next(e for e in result["run_trace"].events if e.agent == "ResearcherAgent")
        assert researcher.tool_call_id == "tc_001"
