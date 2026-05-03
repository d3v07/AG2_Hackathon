"""Tests for the Zone B AG2 group chat (RoundRobinPattern over 7 stages).

Structural tests verify the group chat builds with the expected stages and
ContextVariables. Stage-function tests run each stage in isolation against
ContextVariables, exercising the same logic the round-robin runs.

Integration test (marked) runs the full RoundRobinPattern over the fixture
trace — the existing 3-violation report must come out the other side.
"""
import asyncio
import json
from pathlib import Path

import pytest

from autogen.agentchat.group import ContextVariables

from zone_b.group_chat import (
    _STAGE_NAMES,
    _attribution_stage,
    _contract_checker_stage,
    _trace_collector_stage,
    build_zone_b_stages,
    run_diagnostic_group_chat,
)


@pytest.fixture
def fixture_raw() -> dict:
    return json.loads(Path("zone_b/fixtures/sample_trace.json").read_text())


# ─── structural tests (no LLM, no I/O) ──────────────────────────────────────

class TestGroupChatStructure:
    def test_stage_count_is_seven(self, fixture_raw):
        agents, _ = build_zone_b_stages(fixture_raw)
        assert len(agents) == 7

    def test_stage_names_in_order(self, fixture_raw):
        agents, _ = build_zone_b_stages(fixture_raw)
        assert [a.name for a in agents] == _STAGE_NAMES

    def test_initial_context_carries_raw_trace(self, fixture_raw):
        _, ctx = build_zone_b_stages(fixture_raw)
        assert ctx.get("raw_trace") == fixture_raw
        assert ctx.get("interactive") is False

    def test_interactive_flag_propagates(self, fixture_raw):
        _, ctx = build_zone_b_stages(fixture_raw, interactive=True)
        assert ctx.get("interactive") is True

    def test_stages_have_no_llm_config(self, fixture_raw):
        agents, _ = build_zone_b_stages(fixture_raw)
        for agent in agents:
            assert agent.llm_config is False

    def test_initial_context_has_empty_violations(self, fixture_raw):
        _, ctx = build_zone_b_stages(fixture_raw)
        assert ctx.get("violations") == []
        assert ctx.get("violation_count") == 0


# ─── stage-function unit tests (real Zone B logic, no LLM, no group chat) ───

class TestStageFunctions:
    def test_trace_collector_stage_populates_run_trace(self, fixture_raw):
        ctx = ContextVariables(data={"raw_trace": fixture_raw})
        msg = asyncio.run(_trace_collector_stage(ctx))
        assert "TraceCollector" in msg
        assert ctx.get("run_trace") is not None
        assert ctx.get("context_snapshot") is not None
        assert isinstance(ctx.get("handoff_path"), list)

    def test_trace_collector_stage_handles_missing_input(self):
        ctx = ContextVariables(data={})
        msg = asyncio.run(_trace_collector_stage(ctx))
        assert "missing raw_trace" in msg

    def test_contract_checker_stage_finds_three_violations(self, fixture_raw):
        ctx = ContextVariables(data={"raw_trace": fixture_raw})
        asyncio.run(_trace_collector_stage(ctx))
        msg = asyncio.run(_contract_checker_stage(ctx))
        assert ctx.get("violation_count") == 3
        assert "3 violation" in msg
        violations = ctx.get("violations")
        assert {v.contract_type for v in violations} == {
            "evidence",
            "tool",
            "approval",
        }

    def test_contract_checker_stage_handles_missing_inputs(self):
        ctx = ContextVariables(data={})
        msg = asyncio.run(_contract_checker_stage(ctx))
        assert "missing inputs" in msg

    def test_attribution_stage_handles_no_violations(self, fixture_raw):
        ctx = ContextVariables(data={"raw_trace": fixture_raw})
        asyncio.run(_trace_collector_stage(ctx))
        ctx.set("violations", [])
        msg = asyncio.run(_attribution_stage(ctx))
        attribution = ctx.get("attribution")
        assert attribution["failed_agent"] == ""
        assert attribution["failed_step"] == -1


# ─── integration: full group chat run on fixture (no LLM call required) ─────
#
# RegressionTest hits Daytona only if creds present; without them it returns
# 'error'. Reporter and Attribution call LLM via OpenRouter — if no key,
# they fall back to deterministic text. That makes this test runnable in
# CI without secrets, but still a true end-to-end exercise of the
# RoundRobinPattern wiring.

class TestGroupChatEndToEnd:
    @pytest.mark.integration
    def test_full_group_chat_produces_three_violations_on_fixture(self):
        report = asyncio.run(
            run_diagnostic_group_chat(
                "zone_b/fixtures/sample_trace.json", interactive=False
            )
        )
        assert report["violation_count"] == 3
        assert report["severity_summary"]["high"] == 3
        assert report["failed_agent"] in {"VerifierAgent", "ActionAgent"}
        assert report["approval_status"] == "approved"
