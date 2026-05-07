"""Tests for zone_b/agents/regression_test.py — deterministic parts only."""
import asyncio
import pytest
from shared.models import Violation, RunTrace
from zone_b.agents.regression_test import _parse_status, _fallback_test, run_regression_test


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _v(contract_type: str = "evidence") -> Violation:
    return Violation(
        contract_type=contract_type, severity="high",
        rule="test rule", expected="EXPECTED: x", observed="OBSERVED: y",
        failed_agent="VerifierAgent", failed_step=3,
    )


# ---------------------------------------------------------------------------
# _parse_status
# ---------------------------------------------------------------------------

class TestParseStatus:
    def test_pass_stdout_returns_pass(self):
        assert _parse_status("PASS") == "pass"

    def test_pass_with_whitespace(self):
        assert _parse_status("  PASS  \n") == "pass"

    def test_fail_stdout_returns_fail(self):
        assert _parse_status("FAIL: assertion error") == "fail"

    def test_fail_alone_returns_fail(self):
        assert _parse_status("FAIL") == "fail"

    def test_pass_and_fail_both_present_returns_fail(self):
        assert _parse_status("PASS\nFAIL: something") == "fail"

    def test_empty_string_returns_error(self):
        assert _parse_status("") == "error"

    def test_none_returns_error(self):
        assert _parse_status(None) == "error"

    def test_unrecognised_output_returns_error(self):
        assert _parse_status("some random output") == "error"

    def test_multiline_pass(self):
        assert _parse_status("Running test...\nPASS") == "pass"


# ---------------------------------------------------------------------------
# _fallback_test
# ---------------------------------------------------------------------------

class TestFallbackTest:
    def test_returns_required_keys(self):
        result = _fallback_test("patch", [_v()])
        assert set(result.keys()) == {"test_name", "test_code", "assertions"}

    def test_test_code_is_non_empty(self):
        result = _fallback_test("patch", [_v()])
        assert result["test_code"].strip() != ""

    def test_test_code_prints_pass(self):
        result = _fallback_test("patch", [_v()])
        assert "PASS" in result["test_code"]

    def test_test_code_is_valid_python(self):
        result = _fallback_test("patch", [_v()])
        compile(result["test_code"], "<test>", "exec")

    def test_assertions_list_non_empty(self):
        violations = [_v("evidence"), _v("approval"), _v("tool")]
        result = _fallback_test("patch", violations)
        assert len(result["assertions"]) >= 1

    def test_test_code_covers_routing_contract(self):
        result = _fallback_test("patch", [_v("routing")])
        assert "ReporterAgent" in result["test_code"]
        assert "HumanGateAgent" in result["test_code"]
        assert "routing violation still present" in result["test_code"]
        assert "routing contract is satisfied post-repair" in result["assertions"]

    def test_test_code_covers_schema_contract(self):
        result = _fallback_test("patch", [_v("schema")])
        assert "final_output" in result["test_code"]
        assert "schema violation still present" in result["test_code"]
        assert "schema contract is satisfied post-repair" in result["assertions"]

    def test_test_name_is_snake_case(self):
        result = _fallback_test("patch", [_v()])
        assert " " not in result["test_name"]
        assert result["test_name"].islower() or "_" in result["test_name"]

    def test_fallback_test_code_executes_and_prints_pass(self):
        import subprocess, sys
        result = _fallback_test("patch", [_v()])
        proc = subprocess.run(
            [sys.executable, "-c", result["test_code"]],
            capture_output=True, text=True, timeout=5
        )
        assert "PASS" in proc.stdout


class TestRunRegressionTest:
    def test_bad_generated_test_uses_deterministic_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.regression_test._ask_llm_for_test",
            lambda *_: {
                "test_name": "test_bad_generated",
                "test_code": "print('FAIL: generated assertion is wrong')",
                "assertions": ["bad generated assertion"],
            },
        )
        calls = []

        def fake_run_in_daytona(test_code):
            calls.append(test_code)
            if "generated assertion is wrong" in test_code:
                return ("FAIL: generated assertion is wrong", "sb-generated", "fail")
            return ("PASS", "sb-fallback", "pass")

        monkeypatch.setattr(
            "zone_b.agents.regression_test._run_in_daytona",
            fake_run_in_daytona,
        )

        result = asyncio.run(
            run_regression_test("patch", [_v("evidence")], RunTrace("r", "w", [], None))
        )

        assert result["test_status"] == "pass"
        assert result["test_name"] == "test_repair_resolves_violations"
        assert result["fallback_used"] is True
        assert result["generated_test_status"] == "fail"
        assert len(calls) == 2

    def test_daytona_infrastructure_error_does_not_fake_pass(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.regression_test._ask_llm_for_test",
            lambda *_: {
                "test_name": "test_generated",
                "test_code": "print('PASS')",
                "assertions": ["generated assertion"],
            },
        )
        calls = []

        def fake_run_in_daytona(test_code):
            calls.append(test_code)
            return ("Daytona credentials missing", "no-sandbox", "error")

        monkeypatch.setattr(
            "zone_b.agents.regression_test._run_in_daytona",
            fake_run_in_daytona,
        )

        result = asyncio.run(
            run_regression_test("patch", [_v("evidence")], RunTrace("r", "w", [], None))
        )

        assert result["test_status"] == "error"
        assert result["fallback_used"] is False
        assert result["generated_test_status"] == "error"
        assert len(calls) == 1

    def test_non_list_generated_assertions_fall_back_to_default_assertions(self, monkeypatch):
        monkeypatch.setattr(
            "zone_b.agents.regression_test._ask_llm_for_test",
            lambda *_: {
                "test_name": "test_generated",
                "test_code": "print('PASS evidence')",
                "assertions": "not-a-list",
            },
        )
        monkeypatch.setattr(
            "zone_b.agents.regression_test._run_in_daytona",
            lambda _: ("PASS evidence\nPASS", "sb-001", "pass"),
        )

        result = asyncio.run(
            run_regression_test("patch", [_v("evidence")], RunTrace("r", "w", [], None))
        )

        assert result["assertions"] == []
        assert result["per_violation_results"][0]["assertion"] == (
            "evidence contract is satisfied post-repair"
        )

    def test_local_runner_uses_deterministic_test_without_daytona(self, monkeypatch):
        monkeypatch.setenv("CONCORD_REGRESSION_RUNNER", "local")
        monkeypatch.setattr(
            "zone_b.agents.regression_test._ask_llm_for_test",
            lambda *_: (_ for _ in ()).throw(AssertionError("should not call generator")),
        )
        monkeypatch.setattr(
            "zone_b.agents.regression_test._run_in_daytona",
            lambda *_: (_ for _ in ()).throw(AssertionError("should not call sandbox")),
        )

        result = asyncio.run(
            run_regression_test("patch", [_v("evidence")], RunTrace("r", "w", [], None))
        )

        assert result["test_status"] == "pass"
        assert result["fallback_used"] is True
        assert result["fallback_reason"] == "local_regression_runner"
        assert result["sandbox_id"] == "local-regression"

    def test_local_runner_timeout_reports_error(self, monkeypatch):
        import subprocess

        monkeypatch.setenv("CONCORD_REGRESSION_RUNNER", "local")
        monkeypatch.setattr(
            "zone_b.agents.regression_test.subprocess.run",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                subprocess.TimeoutExpired(cmd="python", timeout=10)
            ),
        )

        result = asyncio.run(
            run_regression_test(
                "patch",
                [_v("evidence")],
                RunTrace("r", "w", [], None),
            )
        )

        assert result["sandbox_id"] == "local-regression"
        assert result["test_status"] == "error"
        assert "timeout" in result["stdout"].lower()
