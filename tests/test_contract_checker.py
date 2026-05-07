"""Tests for zone_b/agents/contract_checker.py"""
import asyncio
import pytest
from shared.models import RunTrace, TraceEvent, ContextSnapshot, Violation
from zone_b.agents.contract_checker import (
    CONTRACTS, _find_failed_step, _generate_violation_text, run_contract_checker
)
from zone_b.agents.trace_collector import run_trace_collector


# ---------------------------------------------------------------------------
# _find_failed_step
# ---------------------------------------------------------------------------

class TestFindFailedStep:
    def _trace_with(self, agents: list[tuple[int, str]]) -> RunTrace:
        events = [
            TraceEvent(step=s, agent=a, type="agent_turn", content="",
                       tool_call_id=None, context_delta={}, handoff_to=None, timestamp=float(s))
            for s, a in agents
        ]
        return RunTrace(run_id="r", workflow_name="w", events=events, final_output=None)

    def test_finds_correct_step(self):
        trace = self._trace_with([(1, "ResearcherAgent"), (3, "VerifierAgent")])
        assert _find_failed_step(trace, "VerifierAgent") == 3

    def test_returns_first_occurrence(self):
        trace = self._trace_with([(2, "VerifierAgent"), (4, "VerifierAgent")])
        assert _find_failed_step(trace, "VerifierAgent") == 2

    def test_returns_minus_one_when_not_found(self):
        trace = self._trace_with([(1, "ResearcherAgent")])
        assert _find_failed_step(trace, "MissingAgent") == -1

    def test_empty_trace(self):
        trace = RunTrace(run_id="r", workflow_name="w", events=[], final_output=None)
        assert _find_failed_step(trace, "AnyAgent") == -1


# ---------------------------------------------------------------------------
# CONTRACTS lambda checks (no LLM)
# ---------------------------------------------------------------------------

class TestContractLambdas:
    def _trace(self, events=None) -> RunTrace:
        return RunTrace(run_id="r", workflow_name="w",
                        events=events or [], final_output=None)

    def _snap(self, verified=0, approval="pending") -> ContextSnapshot:
        return ContextSnapshot(
            retrieved_sources=[], verified_sources_count=verified,
            tool_events=[], approval_status=approval,
            failed_agent=None, failed_step=None, final_output=None
        )

    def _verifier_event(self, tool_call_id=None) -> TraceEvent:
        return TraceEvent(step=3, agent="VerifierAgent", type="agent_turn",
                          content="", tool_call_id=tool_call_id,
                          context_delta={}, handoff_to=None, timestamp=1.0)

    def _contract(self, type_: str) -> dict:
        return next(c for c in CONTRACTS if c["type"] == type_)

    # evidence
    def test_evidence_passes_when_sources_gt_zero(self):
        c = self._contract("evidence")
        assert c["check"](self._trace(), self._snap(verified=1)) is True

    def test_evidence_fails_when_sources_zero(self):
        c = self._contract("evidence")
        assert c["check"](self._trace(), self._snap(verified=0)) is False

    def test_evidence_fails_when_sources_negative(self):
        c = self._contract("evidence")
        assert c["check"](self._trace(), self._snap(verified=-1)) is False

    # tool
    def test_tool_passes_when_verifier_has_tool_call_id(self):
        c = self._contract("tool")
        trace = self._trace([self._verifier_event(tool_call_id="tc_001")])
        assert c["check"](trace, self._snap()) is True

    def test_tool_fails_when_verifier_has_no_tool_call_id(self):
        c = self._contract("tool")
        trace = self._trace([self._verifier_event(tool_call_id=None)])
        assert c["check"](trace, self._snap()) is False

    def test_tool_fails_when_no_verifier_event(self):
        c = self._contract("tool")
        other = TraceEvent(step=1, agent="ResearcherAgent", type="agent_turn",
                           content="", tool_call_id="tc_001",
                           context_delta={}, handoff_to=None, timestamp=0.1)
        trace = self._trace([other])
        assert c["check"](trace, self._snap()) is False

    def test_tool_fails_when_empty_trace(self):
        c = self._contract("tool")
        assert c["check"](self._trace(), self._snap()) is False

    # approval
    def test_approval_passes_when_status_approved(self):
        c = self._contract("approval")
        assert c["check"](self._trace(), self._snap(approval="approved")) is True

    def test_approval_fails_when_status_pending(self):
        c = self._contract("approval")
        assert c["check"](self._trace(), self._snap(approval="pending")) is False

    def test_approval_fails_when_status_rejected(self):
        c = self._contract("approval")
        assert c["check"](self._trace(), self._snap(approval="rejected")) is False

    # contract metadata
    def test_expected_contracts_defined(self):
        types = {c["type"] for c in CONTRACTS}
        assert "evidence" in types
        assert "tool" in types
        assert "approval" in types
        assert "routing" in types
        assert "schema" in types

    def test_all_contracts_have_required_keys(self):
        for c in CONTRACTS:
            assert "type" in c
            assert "severity" in c
            assert "rule" in c
            assert "failed_agent" in c
            assert "check" in c
            assert callable(c["check"])

    def test_contract_severities_match_rules(self):
        severities = {c["type"]: c["severity"] for c in CONTRACTS}
        assert severities["evidence"] == "high"
        assert severities["tool"] == "high"
        assert severities["approval"] == "high"
        assert severities["routing"] == "medium"
        assert severities["schema"] == "medium"

    def test_violation_text_falls_back_when_llm_config_fails(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.contract_checker.get_llm_config",
            lambda: (_ for _ in ()).throw(RuntimeError("missing config")),
        )
        contract = self._contract("evidence")

        expected, observed = _generate_violation_text(contract, self._trace(), self._snap())

        assert expected == contract["rule"]
        assert observed == "contract check failed"


# ---------------------------------------------------------------------------
# run_contract_checker (integration — calls LLM)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRunContractChecker:
    def test_finds_4_violations_on_broken_trace(self, sample_trace_raw):
        collected = asyncio.run(run_trace_collector(sample_trace_raw))
        result = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        assert result["violation_count"] == 4

    def test_returns_correct_keys(self, sample_trace_raw):
        collected = asyncio.run(run_trace_collector(sample_trace_raw))
        result = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        assert set(result.keys()) == {"violations", "violation_count", "severity_summary"}

    def test_violations_are_violation_instances(self, sample_trace_raw):
        collected = asyncio.run(run_trace_collector(sample_trace_raw))
        result = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        for v in result["violations"]:
            assert isinstance(v, Violation)

    def test_all_fixture_contract_types_caught(self, sample_trace_raw):
        collected = asyncio.run(run_trace_collector(sample_trace_raw))
        result = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        types = {v.contract_type for v in result["violations"]}
        assert "evidence" in types
        assert "tool" in types
        assert "approval" in types
        assert "routing" in types

    def test_fixture_violation_severities(self, sample_trace_raw):
        collected = asyncio.run(run_trace_collector(sample_trace_raw))
        result = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        severities = {v.contract_type: v.severity for v in result["violations"]}
        assert severities == {
            "evidence": "high",
            "tool": "high",
            "approval": "high",
            "routing": "medium",
        }

    def test_severity_summary_correct(self, sample_trace_raw):
        collected = asyncio.run(run_trace_collector(sample_trace_raw))
        result = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        assert result["severity_summary"]["high"] == 3
        assert result["severity_summary"]["medium"] == 1
        assert result["severity_summary"]["low"] == 0

    def test_violations_have_non_empty_expected_observed(self, sample_trace_raw):
        collected = asyncio.run(run_trace_collector(sample_trace_raw))
        result = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        for v in result["violations"]:
            assert v.expected
            assert v.observed

    def test_verifier_violations_have_correct_failed_step(self, sample_trace_raw):
        collected = asyncio.run(run_trace_collector(sample_trace_raw))
        result = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        verifier_violations = [v for v in result["violations"]
                                if v.failed_agent == "VerifierAgent"]
        for v in verifier_violations:
            assert v.failed_step == 3

    def test_no_violations_on_clean_trace(self, clean_trace_raw):
        collected = asyncio.run(run_trace_collector(clean_trace_raw))
        result = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        assert result["violation_count"] == 0
        assert result["violations"] == []
