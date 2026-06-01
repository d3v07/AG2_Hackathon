"""Tests for zone_b/agents/reporter.py — deterministic parts only."""
import asyncio
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
        assert set(d.keys()) == {"contract_type", "severity", "rule", "expected", "observed", "failed_agent", "failed_step", "span_id"}
        assert d["span_id"] is None

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
                "test_status": "pass", "stdout": "PASS", "sandbox_id": "sb_001",
                "validation_state": "passed",
                "validation_summary": {"passed": 1, "failed": 0, "skipped": 0, "unavailable": 0, "credential_failure": 0, "execution_error": 0},
                "generated_test_status": "",
                "generated_stdout": "",
                "generated_sandbox_id": "",
                "fallback_used": False,
                "fallback_reason": "",
                "duration_ms": 1250,
                "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
                "cost": {"daytona_seconds": 1.25, "llm_tokens": 12,
                         "llm_cost_usd": 0.00006, "daytona_cost_usd": 0.00025}}

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
        assert result["report"]["validation_state"] == "passed"
        assert result["report"]["validation_summary"]["passed"] == 1

    def test_validation_provenance_fields_propagate(self, monkeypatch):
        monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
        regression = self._regression()
        regression.update({
            "test_status": "pass",
            "generated_test_status": "fail",
            "generated_stdout": "FAIL: generated assertion",
            "generated_sandbox_id": "sb-generated",
            "fallback_used": True,
            "fallback_reason": "generated_test_fail",
        })

        result = asyncio.run(run_reporter(
            _trace(), [_v()], self._attribution(), self._repair(), regression, _snap()
        ))
        report = result["report"]

        assert report["generated_test_status"] == "fail"
        assert report["generated_stdout"] == "FAIL: generated assertion"
        assert report["generated_sandbox_id"] == "sb-generated"
        assert report["fallback_used"] is True
        assert report["fallback_reason"] == "generated_test_fail"

    def test_validation_state_propagates_to_violations_and_regression_tests(self, monkeypatch):
        monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
        regression = self._regression()
        regression["test_status"] = "error"
        regression["validation_state"] = "credential_failure"
        regression["validation_summary"] = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "unavailable": 0,
            "credential_failure": 1,
            "execution_error": 0,
        }
        regression["per_violation_results"] = [
            {
                "contract_type": "evidence",
                "severity": "high",
                "rule": "test rule",
                "failed_agent": "VerifierAgent",
                "failed_step": 3,
                "test_name": "test_fix",
                "assertion": "evidence contract",
                "test_status": "error",
                "validation_state": "credential_failure",
                "stdout": "Daytona credentials missing",
                "sandbox_id": "no-sandbox",
            }
        ]

        result = asyncio.run(run_reporter(
            _trace(), [_v()], self._attribution(), self._repair(), regression, _snap()
        ))
        report = result["report"]

        assert report["validation_state"] == "credential_failure"
        assert report["violations"][0]["validation_state"] == "credential_failure"
        assert report["regression_tests"][0]["validation_state"] == "credential_failure"

    def test_legacy_regression_error_stdout_maps_to_credential_failure(self, monkeypatch):
        monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
        regression = self._regression()
        regression.pop("validation_state", None)
        regression.pop("validation_summary", None)
        regression.pop("per_violation_results", None)
        regression["test_status"] = "error"
        regression["stdout"] = "Daytona error: invalid credentials"
        regression["sandbox_id"] = "no-sandbox"

        result = asyncio.run(run_reporter(
            _trace(), [_v()], self._attribution(), self._repair(), regression, _snap()
        ))
        report = result["report"]

        assert report["validation_state"] == "credential_failure"
        assert report["violations"][0]["validation_state"] == "credential_failure"
        assert report["regression_tests"][0]["validation_state"] == "credential_failure"
        assert report["validation_summary"]["credential_failure"] == 1

    def test_regression_metadata_and_iteration_count_propagate(self, monkeypatch):
        monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
        result = asyncio.run(run_reporter(
            _trace(),
            [_v()],
            self._attribution(),
            self._repair(),
            self._regression(),
            _snap(),
            iteration_count=3,
        ))

        report = result["report"]
        assert report["iteration_count"] == 3
        assert report["sandbox_id"] == "sb_001"
        assert report["regression_duration_ms"] == 1250
        assert report["regression_usage"] == {
            "prompt_tokens": 8,
            "completion_tokens": 4,
            "total_tokens": 12,
        }
        assert report["regression_cost"] == {
            "daytona_seconds": 1.25,
            "llm_tokens": 12,
            "llm_cost_usd": 0.00006,
            "daytona_cost_usd": 0.00025,
        }

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
