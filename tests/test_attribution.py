"""Tests for zone_b/agents/attribution.py — deterministic parts only."""
import asyncio
from shared.models import RunTrace, TraceEvent, ContextSnapshot, Violation
from zone_b.agents.attribution import _deterministic_failed_step, run_attribution


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _trace(*agents: tuple[int, str]) -> RunTrace:
    events = [
        TraceEvent(step=s, agent=a, type="agent_turn", content="",
                   tool_call_id=None, context_delta={}, handoff_to=None, timestamp=float(s))
        for s, a in agents
    ]
    return RunTrace(run_id="r", workflow_name="w", events=events, final_output=None)


def _snap() -> ContextSnapshot:
    return ContextSnapshot(
        retrieved_sources=[], verified_sources_count=0, tool_events=[],
        approval_status="pending", failed_agent=None, failed_step=None, final_output=None,
    )


def _violation(contract_type: str = "evidence", agent: str = "VerifierAgent", step: int = 3) -> Violation:
    return Violation(
        contract_type=contract_type, severity="high",
        rule="test rule", expected="EXPECTED: x", observed="OBSERVED: y",
        failed_agent=agent, failed_step=step,
    )


# ---------------------------------------------------------------------------
# _deterministic_failed_step
# ---------------------------------------------------------------------------

class TestDeterministicFailedStep:
    def test_finds_correct_step(self):
        trace = _trace((1, "ResearcherAgent"), (3, "VerifierAgent"))
        assert _deterministic_failed_step(trace, "VerifierAgent") == 3

    def test_returns_first_occurrence(self):
        trace = _trace((2, "VerifierAgent"), (4, "VerifierAgent"))
        assert _deterministic_failed_step(trace, "VerifierAgent") == 2

    def test_returns_minus_one_when_not_found(self):
        trace = _trace((1, "ResearcherAgent"))
        assert _deterministic_failed_step(trace, "MissingAgent") == -1

    def test_empty_trace(self):
        trace = RunTrace(run_id="r", workflow_name="w", events=[], final_output=None)
        assert _deterministic_failed_step(trace, "AnyAgent") == -1


# ---------------------------------------------------------------------------
# run_attribution — empty violations (no LLM path)
# ---------------------------------------------------------------------------

class TestRunAttributionEmpty:
    def test_empty_violations_returns_empty_result(self):
        result = asyncio.run(run_attribution([], _trace((1, "A")), _snap()))
        assert result["failed_agent"] == ""
        assert result["failed_step"] == -1
        assert result["likely_root_cause"] == "no violations detected"
        assert result["attributions"] == []

    def test_empty_violations_returns_correct_keys(self):
        result = asyncio.run(run_attribution([], _trace((1, "A")), _snap()))
        assert set(result.keys()) == {"failed_agent", "failed_step", "likely_root_cause", "attributions"}


# ---------------------------------------------------------------------------
# run_attribution — fallback path (LLM skipped, deterministic fallback)
# ---------------------------------------------------------------------------

class TestRunAttributionFallback:
    def test_fallback_uses_first_violation_agent(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.attribution._ask_llm_for_attribution",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        v = _violation(agent="VerifierAgent", step=3)
        trace = _trace((1, "ResearcherAgent"), (3, "VerifierAgent"))
        result = asyncio.run(run_attribution([v], trace, _snap()))
        assert result["failed_agent"] == "VerifierAgent"
        assert result["failed_step"] == 3

    def test_fallback_attributions_list_length_matches_violations(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.attribution._ask_llm_for_attribution",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        violations = [
            _violation("evidence", "VerifierAgent", 3),
            _violation("approval", "ActionAgent", 5),
        ]
        trace = _trace((3, "VerifierAgent"), (5, "ActionAgent"))
        result = asyncio.run(run_attribution(violations, trace, _snap()))
        assert len(result["attributions"]) == 2

    def test_fallback_attribution_has_required_keys(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.attribution._ask_llm_for_attribution",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        v = _violation()
        result = asyncio.run(run_attribution([v], _trace((3, "VerifierAgent")), _snap()))
        for attr in result["attributions"]:
            assert "violation_type" in attr
            assert "agent" in attr
            assert "step" in attr
            assert "evidence" in attr

    def test_fallback_root_cause_mentions_agent(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.attribution._ask_llm_for_attribution",
            lambda *_: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        v = _violation(agent="VerifierAgent")
        result = asyncio.run(run_attribution([v], _trace((3, "VerifierAgent")), _snap()))
        assert "VerifierAgent" in result["likely_root_cause"]
