"""Tests for zone_b/agents/regression_test.py — deterministic parts only."""
import pytest
from shared.models import Violation, RunTrace
from zone_b.agents.regression_test import _parse_status, _fallback_test


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
