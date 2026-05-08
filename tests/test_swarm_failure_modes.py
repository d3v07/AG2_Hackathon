"""Failure-mode contract tests for zone_a.swarm.run_swarm.

Five tests specify one contract violation per type (evidence, tool, routing,
approval, schema). Each calls run_swarm with a `failure_mode` kwarg that does
not exist yet — the `failure_mode` parameter lands in #70. They are marked
xfail so CI passes today while the contract is documented.

A sixth test (not xfail) verifies that the Zone B contract checker produces
zero violations when fed a fully clean trace, asserting the baseline contract
path works correctly today.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from zone_b.agents.contract_checker import run_contract_checker
from zone_b.agents.trace_collector import run_trace_collector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_trace_raw() -> dict[str, Any]:
    """Synthesised clean trace — matches the shape zone_a.swarm.run_swarm
    produces in stub mode. All 6 agents fire; all contracts pass."""
    return {
        "run_id": "test_clean",
        "workflow_name": "LiteratureReviewAssistant",
        "events": [
            {
                "step": 1,
                "agent": "ResearcherAgent",
                "type": "agent_turn",
                "content": "Retrieved 2 sources.",
                "tool_call_id": "tc_001",
                "context_delta": {
                    "retrieved_sources": [
                        {"title": "S1", "url": "http://a.example", "snippet": "x"},
                        {"title": "S2", "url": "http://b.example", "snippet": "y"},
                    ],
                    "tool_events": [
                        {
                            "tool_name": "tavily_search",
                            "input": "rq",
                            "output": "2 results",
                            "status": "success",
                            "evidence_id": "ev_001",
                            "timestamp": 0.1,
                        }
                    ],
                },
                "handoff_to": "CriticAgent",
                "timestamp": 0.1,
            },
            {
                "step": 2,
                "agent": "CriticAgent",
                "type": "agent_turn",
                "content": "Sources are solid.",
                "tool_call_id": None,
                "context_delta": {},
                "handoff_to": "VerifierAgent",
                "timestamp": 0.5,
            },
            {
                "step": 3,
                "agent": "VerifierAgent",
                "type": "agent_turn",
                "content": "Verified 2 sources.",
                "tool_call_id": "tc_v01",
                "context_delta": {
                    "verified_sources_count": 2,
                    "approval_status": "approved",
                    "tool_events": [
                        {
                            "tool_name": "tavily_search",
                            "input": "verify",
                            "output": "ok",
                            "status": "success",
                            "evidence_id": "ev_002",
                            "timestamp": 1.0,
                        }
                    ],
                },
                "handoff_to": "ReporterAgent",
                "timestamp": 1.0,
            },
            {
                "step": 4,
                "agent": "ReporterAgent",
                "type": "agent_turn",
                "content": "Final memo written.",
                "tool_call_id": None,
                "context_delta": {
                    "final_output": {
                        "summary": "Stub summary.",
                        "claims": ["c1"],
                        "citations": ["r1"],
                        "risks": [],
                        "next_steps": ["n1"],
                    }
                },
                "handoff_to": "HumanGateAgent",
                "timestamp": 2.0,
            },
            {
                "step": 5,
                "agent": "HumanGateAgent",
                "type": "agent_turn",
                "content": "Approved.",
                "tool_call_id": None,
                "context_delta": {"approval_status": "approved"},
                "handoff_to": "ActionAgent",
                "timestamp": 2.2,
            },
            {
                "step": 6,
                "agent": "ActionAgent",
                "type": "agent_turn",
                "content": "Action taken.",
                "tool_call_id": None,
                "context_delta": {},
                "handoff_to": None,
                "timestamp": 2.5,
            },
        ],
        "final_output": {
            "summary": "Stub summary.",
            "claims": ["c1"],
            "citations": ["r1"],
            "risks": [],
            "next_steps": ["n1"],
        },
    }


def _run_contracts(raw: dict[str, Any]) -> dict[str, Any]:
    """Synchronously collect trace and run all contracts."""
    collected = asyncio.run(run_trace_collector(raw))
    return run_contract_checker(collected["run_trace"], collected["context_snapshot"])


# ---------------------------------------------------------------------------
# Parametrised failure-mode tests (xfail until #70)
#
# Each test calls run_swarm with a `failure_mode` kwarg that does not exist
# yet. The TypeError (or any other Exception) is the expected failure today.
# When #70 lands the `failure_mode` parameter will exist, run_swarm will
# synthesize the violating trace, and the assertion inside will drive the
# test through to RED → GREEN.
# ---------------------------------------------------------------------------

_FAILURE_MODE_CASES: list[tuple[str, str]] = [
    ("force_no_evidence", "evidence"),
    ("force_no_tool_call", "tool"),
    ("force_routing_break", "routing"),
    ("force_no_approval", "approval"),
    ("force_malformed_output", "schema"),
]


def test_failure_mode_rejected_in_live_mode(tmp_path) -> None:
    """failure_mode is a stub-only knob; live mode must raise ValueError so
    a misconfigured production call cannot accidentally inject violations."""
    from zone_a.swarm import run_swarm

    with pytest.raises(ValueError, match="failure_mode is only supported in stub mode"):
        asyncio.run(
            run_swarm(
                mode="live",
                failure_mode="force_no_evidence",
                task="t",
                research_question="rq",
                run_id="test_live_rejects_failure_mode",
                output_path=tmp_path / "trace.json",
            )
        )


@pytest.mark.parametrize("failure_mode,expected_contract_type", _FAILURE_MODE_CASES)
def test_failure_mode_produces_expected_violation(
    failure_mode: str,
    expected_contract_type: str,
    tmp_path,
) -> None:
    """run_swarm(mode='stub', failure_mode=X) must produce exactly the
    contract violation type for that mode after Zone B contract checking.
    """
    from zone_a.swarm import run_swarm  # local import — module may not be on path in all envs

    result = asyncio.run(
        run_swarm(
            mode="stub",
            failure_mode=failure_mode,
            task="t",
            research_question="rq",
            run_id=f"test_{failure_mode}",
            output_path=tmp_path / "trace.json",
        )
    )

    raw = json.loads(Path(result["trace_path"]).read_text())
    checker_result = _run_contracts(raw)

    violation_types = {v.contract_type for v in checker_result["violations"]}
    assert violation_types == {expected_contract_type}, (
        f"Expected exactly violations of type '{expected_contract_type}' "
        f"for failure_mode='{failure_mode}', got: {violation_types}"
    )


# ---------------------------------------------------------------------------
# Clean default test — must pass today (no xfail)
#
# Asserts the Zone B contract checker finds zero violations on a
# shape-compatible clean stub trace. This validates the assertion path before
# #66 (stub mode) and #70 (failure_mode) land, and acts as the passing
# baseline anchor once they do.
# ---------------------------------------------------------------------------

def test_clean_default_stub_trace_produces_zero_violations() -> None:
    """Zone B contract checker returns zero violations on a fully clean trace.

    This test does NOT call run_swarm — stub mode (#66) is not yet implemented.
    Once #66 lands, this test should be updated to call:
        run_swarm(mode="stub", task="t", research_question="rq", run_id="test_clean")
    and read its trace_path.
    """
    raw = _clean_trace_raw()
    result = _run_contracts(raw)

    assert result["violation_count"] == 0, (
        f"Expected 0 violations on clean trace, got {result['violation_count']}: "
        f"{[v.contract_type for v in result['violations']]}"
    )
    assert result["violations"] == []
