"""Sprint 14 #69 — clean-path Zone A test.

Asserts the Zone A swarm's success-first contract: a normal stub run
produces verifier tool evidence, approval gating, action recording, and
ZERO contract violations when fed through the Zone B contract checker.

Live mode (real LLM + Tavily) is exercised by an opt-in test that runs
only when OPENROUTER_API_KEY is set — see test_clean_path_live_mode.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from zone_a.swarm import run_swarm
from zone_b.agents.contract_checker import run_contract_checker
from zone_b.agents.trace_collector import run_trace_collector


def _run(coro):
    return asyncio.run(coro)


def _serialize(obj: Any) -> Any:
    if is_dataclass(obj):
        return _serialize(asdict(obj))
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


def _stub_run(tmp_path: Path) -> dict[str, Any]:
    output = tmp_path / "clean_path_trace.json"
    result = _run(
        run_swarm(
            task="Survey reliability patterns in multi-agent systems",
            research_question="What architectural patterns improve MAS reliability?",
            run_id="clean_path_001",
            output_path=output,
            mode="stub",
        )
    )
    return result


def _zone_b_violations(trace_path: str | Path) -> list[Any]:
    raw = json.loads(Path(trace_path).read_text())
    collected = _run(run_trace_collector(raw))
    checked = run_contract_checker(collected["run_trace"], collected["context_snapshot"])
    return checked["violations"]


# ─── all 6 agents fired ────────────────────────────────────────────────────────


def test_all_six_agents_fire(tmp_path):
    result = _stub_run(tmp_path)
    agents = [e.agent for e in result["events"]]
    assert agents == [
        "ResearcherAgent",
        "CriticAgent",
        "VerifierAgent",
        "ReporterAgent",
        "HumanGateAgent",
        "ActionAgent",
    ]


def test_swarm_does_not_terminate_early(tmp_path):
    result = _stub_run(tmp_path)
    assert result["terminated_early"] is False


def test_last_agent_is_action(tmp_path):
    result = _stub_run(tmp_path)
    assert result["last_agent"] == "ActionAgent"


# ─── verifier tool evidence ────────────────────────────────────────────────────


def test_verifier_tool_call_id_matches_pattern(tmp_path):
    result = _stub_run(tmp_path)
    verifier_events = [e for e in result["events"] if e.agent == "VerifierAgent"]
    assert verifier_events
    tcid = verifier_events[0].tool_call_id
    assert tcid is not None
    assert re.match(r"^tc_[a-zA-Z0-9_]+$", tcid), f"tool_call_id {tcid!r} does not match ^tc_*"


def test_verified_sources_count_is_at_least_one(tmp_path):
    result = _stub_run(tmp_path)
    ctx = result["context"]
    assert ctx.get("verified_sources_count", 0) >= 1


# ─── approval gating ───────────────────────────────────────────────────────────


def test_approval_status_is_approved(tmp_path):
    result = _stub_run(tmp_path)
    assert result["context"].get("approval_status") == "approved"


def test_approval_granted_is_true(tmp_path):
    result = _stub_run(tmp_path)
    assert result["context"].get("approval_granted") is True


# ─── final_output schema ───────────────────────────────────────────────────────


def test_final_output_has_all_five_required_fields(tmp_path):
    result = _stub_run(tmp_path)
    final = result["context"].get("final_output")
    assert final is not None
    for key in ("summary", "claims", "citations", "risks", "next_steps"):
        assert key in final, f"final_output missing key: {key}"


# ─── ZERO contract violations (the headline assertion) ────────────────────────


def test_zone_b_yields_zero_violations(tmp_path):
    result = _stub_run(tmp_path)
    violations = _zone_b_violations(result["trace_path"])
    assert violations == [], (
        "Clean-path stub run must produce zero contract violations. "
        f"Got {len(violations)}: " + ", ".join(
            f"[{v.severity}] {v.contract_type}: {v.rule}" for v in violations
        )
    )


# ─── live mode opt-in ──────────────────────────────────────────────────────────


@pytest.mark.skipif(
    os.environ.get("CONCORD_RUN_LIVE_TESTS") != "1",
    reason="live mode requires explicit opt-in: CONCORD_RUN_LIVE_TESTS=1",
)
def test_clean_path_live_mode_smoke(tmp_path):
    """Optional smoke run against a real LLM. Only runs when explicitly
    opted in via CONCORD_RUN_LIVE_TESTS=1 (LLM responses are non-deterministic
    so we can't assert zero violations — only that the swarm completed).
    """
    output = tmp_path / "live_clean_path_trace.json"
    result = _run(
        run_swarm(
            task="Survey reliability patterns in multi-agent systems",
            research_question="What architectural patterns improve MAS reliability?",
            run_id="live_clean_path_001",
            output_path=output,
            mode="live",
        )
    )
    # Live LLM behavior is non-deterministic — only assert the swarm produced
    # a trace and reached *some* agent. Determinism is the stub mode's job.
    assert result["last_agent"] is not None
    assert Path(result["trace_path"]).exists()
