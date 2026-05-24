"""Tests for zone_a.swarm.run_swarm stub mode (#66).

Verifies that mode="stub" produces a deterministic, LLM-free trace that
passes all Zone B contract checks with zero violations.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from zone_a.swarm import run_swarm
from zone_b.agents.contract_checker import run_contract_checker
from zone_b.agents.trace_collector import run_trace_collector


# ─── helpers ────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


def _stub_result(tmp_path: Path) -> dict:
    return _run(
        run_swarm(
            task="Test task",
            research_question="What is the effect of X on Y?",
            run_id="test_stub_001",
            output_path=tmp_path / "stub_trace.json",
            mode="stub",
        )
    )


# ─── shape tests ─────────────────────────────────────────────────────────────

class TestStubShape:
    def test_returns_expected_shape(self, tmp_path):
        result = _stub_result(tmp_path)
        assert "events" in result
        assert "context" in result
        assert "last_agent" in result
        assert "terminated_early" in result
        assert "trace_path" in result

    def test_stub_produces_six_events(self, tmp_path):
        result = _stub_result(tmp_path)
        assert len(result["events"]) == 6

    def test_stub_agents_fire_in_order(self, tmp_path):
        result = _stub_result(tmp_path)
        agents = [e.agent for e in result["events"]]
        assert agents == [
            "ResearcherAgent",
            "CriticAgent",
            "VerifierAgent",
            "ReporterAgent",
            "HumanGateAgent",
            "ActionAgent",
        ]

    def test_terminated_early_is_false_for_clean_stub(self, tmp_path):
        result = _stub_result(tmp_path)
        assert result["terminated_early"] is False

    def test_last_agent_is_action_agent(self, tmp_path):
        result = _stub_result(tmp_path)
        assert result["last_agent"] == "ActionAgent"


# ─── verifier tests ──────────────────────────────────────────────────────────

class TestStubVerifier:
    def test_verifier_tool_call_id_matches_pattern(self, tmp_path):
        result = _stub_result(tmp_path)
        verifier_event = next(e for e in result["events"] if e.agent == "VerifierAgent")
        assert verifier_event.tool_call_id is not None
        assert re.match(r"^tc_[a-zA-Z0-9_]+$", verifier_event.tool_call_id)

    def test_verifier_tool_call_id_is_tc_v01(self, tmp_path):
        result = _stub_result(tmp_path)
        verifier_event = next(e for e in result["events"] if e.agent == "VerifierAgent")
        assert verifier_event.tool_call_id == "tc_v01"

    def test_verifier_verified_sources_count_is_one(self, tmp_path):
        result = _stub_result(tmp_path)
        verifier_event = next(e for e in result["events"] if e.agent == "VerifierAgent")
        assert verifier_event.context_delta.get("verified_sources_count") == 1


# ─── approval tests ───────────────────────────────────────────────────────────

class TestStubApproval:
    def test_approval_status_is_approved(self, tmp_path):
        result = _stub_result(tmp_path)
        ctx = result["context"]
        assert ctx.get("approval_status") == "approved"

    def test_approval_granted_is_true(self, tmp_path):
        result = _stub_result(tmp_path)
        ctx = result["context"]
        assert ctx.get("approval_granted") is True

    def test_human_gate_event_context_delta_has_approved(self, tmp_path):
        result = _stub_result(tmp_path)
        gate_event = next(e for e in result["events"] if e.agent == "HumanGateAgent")
        assert gate_event.context_delta.get("approval_status") == "approved"


# ─── final_output tests ───────────────────────────────────────────────────────

class TestStubFinalOutput:
    def test_final_output_has_all_required_fields(self, tmp_path):
        result = _stub_result(tmp_path)
        reporter_event = next(e for e in result["events"] if e.agent == "ReporterAgent")
        final_output = reporter_event.context_delta.get("final_output")
        assert isinstance(final_output, dict)
        required = {"summary", "claims", "citations", "risks", "next_steps"}
        assert required.issubset(final_output.keys())

    def test_final_output_summary_is_non_empty(self, tmp_path):
        result = _stub_result(tmp_path)
        reporter_event = next(e for e in result["events"] if e.agent == "ReporterAgent")
        final_output = reporter_event.context_delta.get("final_output")
        assert final_output["summary"]

    def test_context_final_output_matches_reporter_event(self, tmp_path):
        result = _stub_result(tmp_path)
        reporter_event = next(e for e in result["events"] if e.agent == "ReporterAgent")
        assert result["context"].get("final_output") == reporter_event.context_delta.get("final_output")


# ─── Zone B contract check ────────────────────────────────────────────────────

class TestStubZoneBContracts:
    def test_stub_trace_yields_zero_violations(self, tmp_path):
        """Stub trace fed through Zone B contract checker produces zero violations."""
        _run(
            run_swarm(
                task="Test task",
                research_question="What is the effect of X on Y?",
                run_id="test_stub_zoneb",
                output_path=tmp_path / "stub_trace.json",
                mode="stub",
            )
        )
        raw = json.loads((tmp_path / "stub_trace.json").read_text())
        collected = _run(run_trace_collector(raw))
        result = run_contract_checker(collected["run_trace"], collected["context_snapshot"])
        assert result["violation_count"] == 0, (
            f"Expected 0 violations but got {result['violation_count']}: "
            + ", ".join(f"[{v.severity}] {v.contract_type}: {v.rule}" for v in result["violations"])
        )


# ─── live mode default unchanged ─────────────────────────────────────────────

class TestLiveModeDefault:
    def test_mode_default_is_live(self):
        sig = inspect.signature(run_swarm)
        mode_param = sig.parameters.get("mode")
        assert mode_param is not None
        assert mode_param.default == "live"


# ─── unknown mode raises ValueError ───────────────────────────────────────────

class TestUnknownMode:
    def test_unknown_mode_raises_valueerror(self, tmp_path):
        with pytest.raises(ValueError, match="unknown mode"):
            _run(
                run_swarm(
                    task="t",
                    research_question="rq",
                    run_id="test_bad_mode",
                    output_path=tmp_path / "trace.json",
                    mode="bogus",  # type: ignore[arg-type]
                )
            )


# ─── Tavily not called in stub ────────────────────────────────────────────────

class TestStubNoTavily:
    def test_stub_does_not_call_tavily(self, tmp_path):
        # TavilyClient is imported inside _build_initial_message — patch the
        # actual import target plus the build helper so a regression that
        # routes stub mode through live's initial-message path is caught.
        with (
            patch("tavily.TavilyClient") as mock_tavily_cls,
            patch("zone_a.swarm._build_initial_message") as mock_build_initial,
        ):
            with patch.dict("os.environ", {"TAVILY_API_KEY": "fake-key-for-test"}):
                _run(
                    run_swarm(
                        task="Test task",
                        research_question="rq",
                        run_id="test_no_tavily",
                        output_path=tmp_path / "stub_trace.json",
                        mode="stub",
                    )
                )
            mock_tavily_cls.assert_not_called()
            mock_build_initial.assert_not_called()
