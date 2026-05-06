"""Integration tests — Zone A trace schema compatibility with Zone B pipeline.

All tests are deterministic (no LLM), using fixture trace only.
Tests marked integration require live API keys and are skipped in CI.
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from shared.models import ContextSnapshot, RunTrace, TraceEvent, ToolEvent
from zone_b.agents.contract_checker import CONTRACTS, run_contract_checker
from zone_b.agents.trace_collector import (
    _build_context_snapshot,
    _parse_trace_events,
    run_trace_collector,
)
from zone_a.run import _to_trace_event


FIXTURE_PATH = Path("zone_b/fixtures/sample_trace.json")


@pytest.fixture
def fixture_raw() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture
def fixture_collected(fixture_raw) -> dict:
    return asyncio.run(run_trace_collector(fixture_raw))


# ── Zone A trace → Zone B schema compatibility ────────────────────────────────

class TestZoneATraceSchema:
    def test_fixture_trace_parses_without_error(self, fixture_raw):
        events = _parse_trace_events(fixture_raw["events"])
        assert len(events) == 5

    def test_all_events_are_trace_event_instances(self, fixture_raw):
        events = _parse_trace_events(fixture_raw["events"])
        assert all(isinstance(e, TraceEvent) for e in events)

    def test_required_fields_present_on_all_events(self, fixture_raw):
        events = _parse_trace_events(fixture_raw["events"])
        for e in events:
            assert isinstance(e.step, int)
            assert isinstance(e.agent, str) and e.agent
            assert e.type == "agent_turn"
            assert isinstance(e.content, str)
            assert isinstance(e.context_delta, dict)
            assert isinstance(e.timestamp, float)

    def test_researcher_has_tool_call_id(self, fixture_raw):
        events = _parse_trace_events(fixture_raw["events"])
        researcher = next(e for e in events if e.agent == "ResearcherAgent")
        assert researcher.tool_call_id is not None

    def test_tool_events_parsed_to_dataclass(self, fixture_raw):
        events = _parse_trace_events(fixture_raw["events"])
        researcher = next(e for e in events if e.agent == "ResearcherAgent")
        tool_events = researcher.context_delta.get("tool_events", [])
        assert len(tool_events) > 0
        assert all(isinstance(te, ToolEvent) for te in tool_events)

    def test_context_snapshot_builds_from_trace(self, fixture_raw):
        events = _parse_trace_events(fixture_raw["events"])
        snap = _build_context_snapshot(events)
        assert isinstance(snap, ContextSnapshot)
        assert isinstance(snap.retrieved_sources, list)
        assert len(snap.retrieved_sources) > 0

    def test_handoff_path_is_full_5_agents(self, fixture_collected):
        path = fixture_collected["handoff_path"]
        assert path == [
            "ResearcherAgent", "CriticAgent", "VerifierAgent",
            "ReporterAgent", "ActionAgent"
        ]

    def test_zone_a_agent_dicts_convert_to_trace_events(self):
        import time
        mocks = [
            {"step": 1, "agent": "ResearcherAgent", "type": "agent_turn",
             "content": "s", "tool_call_id": "tc_001",
             "context_delta": {"retrieved_sources": [], "tool_events": []},
             "handoff_to": "CriticAgent", "timestamp": time.time()},
            {"step": 2, "agent": "CriticAgent", "type": "agent_turn",
             "content": "s", "tool_call_id": None,
             "context_delta": {}, "handoff_to": "VerifierAgent", "timestamp": time.time()},
            {"step": 3, "agent": "VerifierAgent", "type": "agent_turn",
             "content": "s", "tool_call_id": None,
             "context_delta": {"verified_sources_count": 0},
             "handoff_to": "ReporterAgent", "timestamp": time.time()},
            {"step": 4, "agent": "ReporterAgent", "type": "agent_turn",
             "content": "s", "tool_call_id": None,
             "context_delta": {"final_output": {"summary": "s"}},
             "handoff_to": "ActionAgent", "timestamp": time.time()},
            {"step": 5, "agent": "ActionAgent", "type": "agent_turn",
             "content": "s", "tool_call_id": None,
             "context_delta": {}, "handoff_to": None, "timestamp": time.time()},
        ]
        for m in mocks:
            ev = _to_trace_event(m)
            assert isinstance(ev, TraceEvent)


# ── Contract violation detection ─────────────────────────────────────────────

class TestContractViolationDetection:
    def test_exactly_4_violations_on_fixture(self, fixture_collected):
        checked = run_contract_checker(
            fixture_collected["run_trace"],
            fixture_collected["context_snapshot"],
        )
        assert checked["violation_count"] == 4

    def test_fixture_violation_severity_summary(self, fixture_collected):
        checked = run_contract_checker(
            fixture_collected["run_trace"],
            fixture_collected["context_snapshot"],
        )
        assert checked["severity_summary"]["high"] == 3
        assert checked["severity_summary"]["medium"] == 1
        assert checked["severity_summary"]["low"] == 0

    def test_violation_types_include_routing(self, fixture_collected):
        checked = run_contract_checker(
            fixture_collected["run_trace"],
            fixture_collected["context_snapshot"],
        )
        types = {v.contract_type for v in checked["violations"]}
        assert types == {"evidence", "tool", "approval", "routing"}

    def test_evidence_violation_failed_agent_is_verifier(self, fixture_collected):
        checked = run_contract_checker(
            fixture_collected["run_trace"],
            fixture_collected["context_snapshot"],
        )
        ev = next(v for v in checked["violations"] if v.contract_type == "evidence")
        assert ev.failed_agent == "VerifierAgent"
        assert ev.failed_step == 3

    def test_approval_violation_failed_agent_is_action(self, fixture_collected):
        checked = run_contract_checker(
            fixture_collected["run_trace"],
            fixture_collected["context_snapshot"],
        )
        av = next(v for v in checked["violations"] if v.contract_type == "approval")
        assert av.failed_agent == "ActionAgent"
        assert av.failed_step == 5

    def test_clean_trace_has_zero_violations(self, clean_trace_raw):
        raw_events = _parse_trace_events(clean_trace_raw["events"])
        snap = _build_context_snapshot(raw_events)
        run_trace = RunTrace(
            run_id=clean_trace_raw["run_id"],
            workflow_name=clean_trace_raw["workflow_name"],
            events=raw_events,
            final_output=clean_trace_raw.get("final_output"),
        )
        checked = run_contract_checker(run_trace, snap)
        assert checked["violation_count"] == 0


# ── run_all.py --fixture subprocess test ─────────────────────────────────────

@pytest.mark.integration
class TestRunAllFixtureMode:
    def test_fixture_mode_exits_zero(self):
        """run_all.py --fixture must complete without error (no API keys needed for Zone A)."""
        result = subprocess.run(
            [sys.executable, "run_all.py", "--fixture"],
            capture_output=True, text=True, timeout=120
        )
        assert result.returncode == 0, f"run_all.py failed:\n{result.stderr}"

    def test_fixture_mode_reports_4_violations(self):
        result = subprocess.run(
            [sys.executable, "run_all.py", "--fixture"],
            capture_output=True, text=True, timeout=120
        )
        assert "Violations        : 4" in result.stdout

    def test_fixture_mode_report_contains_verifier_agent(self):
        result = subprocess.run(
            [sys.executable, "run_all.py", "--fixture"],
            capture_output=True, text=True, timeout=120
        )
        assert "VerifierAgent" in result.stdout

    def test_fixture_mode_approval_status_approved(self):
        result = subprocess.run(
            [sys.executable, "run_all.py", "--fixture"],
            capture_output=True, text=True, timeout=120
        )
        assert "Approval status   : approved" in result.stdout
