"""Tests for zone_b/agents/reporter.py — deterministic parts only."""
import asyncio
import pytest
from shared.models import RunTrace, TraceEvent, ContextSnapshot, Violation
from zone_b.agents.reporter import _violations_to_dicts, _severity_summary, run_reporter


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _v(contract_type: str = "evidence", severity: str = "high",
       agent: str = "VerifierAgent", step: int = 3) -> Violation:
    return Violation(
        contract_type=contract_type, severity=severity,
        rule="test rule", expected="EXPECTED: x", observed="OBSERVED: y",
        failed_agent=agent, failed_step=step,
    )


def _trace() -> RunTrace:
    return RunTrace(
        run_id="run_041", workflow_name="LiteratureReviewAssistant",
        events=[
            TraceEvent(step=3, agent="VerifierAgent", type="agent_turn", content="",
                       tool_call_id=None, context_delta={}, handoff_to=None, timestamp=1.0)
        ],
        final_output=None,
    )


def _snap() -> ContextSnapshot:
    return ContextSnapshot(
        retrieved_sources=[], verified_sources_count=0, tool_events=[],
        approval_status="pending", failed_agent=None, failed_step=None, final_output=None,
    )


# ---------------------------------------------------------------------------
# _violations_to_dicts
# ---------------------------------------------------------------------------

class TestViolationsToDicts:
    def test_empty_list(self):
        assert _violations_to_dicts([]) == []

    def test_single_violation_has_all_keys(self):
        result = _violations_to_dicts([_v()])
        assert len(result) == 1
        d = result[0]
        assert set(d.keys()) == {"contract_type", "severity", "rule", "expected", "observed", "failed_agent", "failed_step"}

    def test_values_match_violation(self):
        v = _v("approval", "high", "ActionAgent", 5)
        result = _violations_to_dicts([v])
        assert result[0]["contract_type"] == "approval"
        assert result[0]["failed_agent"] == "ActionAgent"
        assert result[0]["failed_step"] == 5

    def test_multiple_violations_preserve_order(self):
        violations = [_v("evidence"), _v("tool"), _v("approval")]
        result = _violations_to_dicts(violations)
        assert len(result) == 3
        assert result[0]["contract_type"] == "evidence"
        assert result[1]["contract_type"] == "tool"
        assert result[2]["contract_type"] == "approval"


# ---------------------------------------------------------------------------
# _severity_summary
# ---------------------------------------------------------------------------

class TestSeveritySummary:
    def test_empty_violations(self):
        result = _severity_summary([])
        assert result == {"high": 0, "medium": 0, "low": 0}

    def test_counts_high_correctly(self):
        result = _severity_summary([_v("evidence", "high"), _v("tool", "high")])
        assert result["high"] == 2
        assert result["medium"] == 0

    def test_counts_mixed_severities(self):
        violations = [_v(severity="high"), _v(severity="medium"), _v(severity="low"), _v(severity="high")]
        result = _severity_summary(violations)
        assert result["high"] == 2
        assert result["medium"] == 1
        assert result["low"] == 1

    def test_three_high_violations(self):
        violations = [_v("evidence"), _v("tool"), _v("approval")]
        result = _severity_summary(violations)
        assert result["high"] == 3


# ---------------------------------------------------------------------------
# run_reporter — output shape (LLM skipped via monkeypatch)
# ---------------------------------------------------------------------------

class TestRunReporterShape:
    def _attribution(self):
        return {"failed_agent": "VerifierAgent", "failed_step": 3,
                "likely_root_cause": "VerifierAgent broke contract", "attributions": []}

    def _repair(self):
        patch = {"contract_type": "evidence", "severity": "high", "rule": "test rule",
                 "failed_agent": "VerifierAgent", "failed_step": 3,
                 "repair_patch": "Add Guardrail", "affected_primitive": "Guardrail",
                 "patch_code": "# patch", "expected_impact": "fixes it", "confidence": 0.85}
        return {"patches": [patch], "repair_patch": "Add Guardrail",
                "affected_primitive": "Guardrail", "patch_code": "# patch",
                "expected_impact": "fixes it", "confidence": 0.85}

    def _regression(self):
        return {"test_name": "test_fix", "test_code": "print('PASS')", "assertions": [],
                "test_status": "pass", "stdout": "PASS", "sandbox_id": "sb_001"}

    def test_report_has_required_keys(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.reporter._ask_llm_for_narrative",
            lambda _: "narrative text"
        )
        result = asyncio.run(run_reporter(
            _trace(), [_v()], self._attribution(), self._repair(), self._regression(), _snap()
        ))
        report = result["report"]
        required = {"run_id", "workflow_name", "violation_count", "severity_summary",
                    "failed_agent", "failed_step", "likely_root_cause", "repair_patch",
                    "affected_primitive", "patch_code", "regression_test_status",
                    "repair_confidence", "approval_status", "violations", "patches",
                    "narrative"}
        assert required.issubset(set(report.keys()))

    def test_report_includes_repair_patches(self, monkeypatch):
        monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
        result = asyncio.run(run_reporter(
            _trace(), [_v()], self._attribution(), self._repair(), self._regression(), _snap()
        ))

        assert result["report"]["patches"] == self._repair()["patches"]

    def test_report_preserves_multiple_repair_patches(self, monkeypatch):
        monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
        repair = self._repair()
        second_patch = dict(repair["patches"][0])
        second_patch.update({
            "contract_type": "tool",
            "severity": "high",
            "rule": "tool rule",
            "repair_patch": "Add OnContextCondition",
            "affected_primitive": "OnContextCondition",
            "patch_code": "# second patch",
        })
        repair["patches"] = [repair["patches"][0], second_patch]

        result = asyncio.run(run_reporter(
            _trace(),
            [_v(), _v("tool")],
            self._attribution(),
            repair,
            self._regression(),
            _snap(),
        ))

        assert result["report"]["patches"] == repair["patches"]
        assert result["report"]["patches"][1]["repair_patch"] == "Add OnContextCondition"
        assert result["report"]["repair_patch"] == "Add Guardrail"

    def test_violation_count_matches(self, monkeypatch):
        monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
        result = asyncio.run(run_reporter(
            _trace(), [_v(), _v("tool")], self._attribution(), self._repair(), self._regression(), _snap()
        ))
        assert result["report"]["violation_count"] == 2

    def test_run_id_propagated(self, monkeypatch):
        monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
        result = asyncio.run(run_reporter(
            _trace(), [_v()], self._attribution(), self._repair(), self._regression(), _snap()
        ))
        assert result["report"]["run_id"] == "run_041"

    def test_regression_status_propagated(self, monkeypatch):
        monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
        result = asyncio.run(run_reporter(
            _trace(), [_v()], self._attribution(), self._repair(), self._regression(), _snap()
        ))
        assert result["report"]["regression_test_status"] == "pass"

    def test_fallback_narrative_on_llm_failure(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.reporter._ask_llm_for_narrative",
            lambda _: (_ for _ in ()).throw(RuntimeError("LLM down"))
        )
        result = asyncio.run(run_reporter(
            _trace(), [_v()], self._attribution(), self._repair(), self._regression(), _snap()
        ))
        assert result["report"]["narrative"] != ""
        assert isinstance(result["report"]["narrative"], str)
