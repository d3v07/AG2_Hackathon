"""Repair-test-iterate loop tests."""
from __future__ import annotations

import asyncio

from shared.models import RunTrace, Violation
from zone_b.orchestrator import run_repair_test_iterations


def _violation() -> Violation:
    return Violation(
        contract_type="evidence",
        severity="high",
        rule="verified sources required",
        expected="verified_sources_count > 0",
        observed="verified_sources_count = 0",
        failed_agent="ReporterAgent",
        failed_step=3,
    )


def _repair(iteration: int) -> dict:
    return {
        "patches": [
            {
                "contract_type": "evidence",
                "severity": "high",
                "rule": "verified sources required",
                "failed_agent": "ReporterAgent",
                "failed_step": 3,
                "repair_patch": f"patch-v{iteration}",
                "affected_primitive": "Guardrail",
                "patch_code": f"# patch-v{iteration}",
                "expected_impact": "prevents unsupported output",
                "confidence": 0.85,
            }
        ],
        "repair_patch": f"patch-v{iteration}",
        "affected_primitive": "Guardrail",
        "patch_code": f"# patch-v{iteration}",
        "expected_impact": "prevents unsupported output",
        "confidence": 0.85,
    }


def _regression(status: str, iteration: int = 1) -> dict:
    return {
        "test_name": "test_fix",
        "test_code": "print('PASS')",
        "assertions": ["evidence contract is satisfied"],
        "test_status": status,
        "stdout": "PASS" if status == "pass" else "FAIL: still broken",
        "sandbox_id": "sb-001",
        "per_violation_results": [
            {
                "contract_type": "evidence",
                "severity": "high",
                "rule": "verified sources required",
                "failed_agent": "ReporterAgent",
                "failed_step": 3,
                "test_name": "test_fix_1_evidence",
                "assertion": "evidence contract is satisfied",
                "test_status": status,
                "stdout": "PASS" if status == "pass" else "FAIL: still broken",
                "sandbox_id": "sb-001",
            }
        ],
        "per_violation_summary": {
            "pass": 1 if status == "pass" else 0,
            "fail": 1 if status == "fail" else 0,
            "error": 1 if status == "error" else 0,
        },
        "duration_ms": iteration * 100,
        "usage": {
            "prompt_tokens": iteration,
            "completion_tokens": iteration * 2,
            "total_tokens": iteration * 3,
        },
        "cost": {
            "daytona_seconds": iteration / 10,
            "llm_tokens": iteration * 3,
            "llm_cost_usd": iteration / 10000,
            "daytona_cost_usd": iteration / 1000,
        },
    }


def test_retries_failed_regression_then_converges():
    repair_calls: list[int] = []
    regression_inputs: list[str] = []

    async def repair_func(*_args):
        repair_calls.append(len(repair_calls) + 1)
        return _repair(repair_calls[-1])

    async def regression_func(repair_patch, *_args):
        regression_inputs.append(repair_patch)
        return _regression(
            "fail" if len(regression_inputs) == 1 else "pass",
            len(regression_inputs),
        )

    result = asyncio.run(
        run_repair_test_iterations(
            [_violation()],
            RunTrace("run-1", "workflow", [], None),
            "ReporterAgent",
            3,
            repair_func=repair_func,
            regression_func=regression_func,
        )
    )

    assert repair_calls == [1, 2]
    assert regression_inputs == ["patch-v1", "patch-v2"]
    assert result["iteration_count"] == 2
    assert result["repair"]["repair_patch"] == "patch-v2"
    assert result["regression"]["test_status"] == "pass"
    assert result["regression"]["duration_ms"] == 300
    assert result["regression"]["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 6,
        "total_tokens": 9,
    }
    assert result["regression"]["cost"] == {
        "daytona_seconds": 0.3,
        "llm_tokens": 9,
        "llm_cost_usd": 0.0003,
        "daytona_cost_usd": 0.003,
    }
    assert len(result["regression"]["regression_attempts"]) == 2


def test_stops_after_three_failed_iterations():
    repair_calls: list[int] = []
    regression_inputs: list[str] = []

    async def repair_func(*_args):
        repair_calls.append(len(repair_calls) + 1)
        return _repair(repair_calls[-1])

    async def regression_func(repair_patch, *_args):
        regression_inputs.append(repair_patch)
        return _regression("fail", len(regression_inputs))

    result = asyncio.run(
        run_repair_test_iterations(
            [_violation()],
            RunTrace("run-1", "workflow", [], None),
            "ReporterAgent",
            3,
            repair_func=repair_func,
            regression_func=regression_func,
        )
    )

    assert repair_calls == [1, 2, 3]
    assert regression_inputs == ["patch-v1", "patch-v2", "patch-v3"]
    assert result["iteration_count"] == 3
    assert result["repair"]["repair_patch"] == "patch-v3"
    assert result["regression"]["test_status"] == "fail"
    assert result["regression"]["duration_ms"] == 600


def test_does_not_retry_on_regression_infrastructure_error():
    repair_calls: list[int] = []
    regression_inputs: list[str] = []

    async def repair_func(*_args):
        repair_calls.append(len(repair_calls) + 1)
        return _repair(repair_calls[-1])

    async def regression_func(repair_patch, *_args):
        regression_inputs.append(repair_patch)
        result = _regression("error")
        result["stdout"] = "Daytona credentials missing"
        result["per_violation_results"][0]["stdout"] = "Daytona credentials missing"
        return result

    result = asyncio.run(
        run_repair_test_iterations(
            [_violation()],
            RunTrace("run-1", "workflow", [], None),
            "ReporterAgent",
            3,
            repair_func=repair_func,
            regression_func=regression_func,
        )
    )

    assert repair_calls == [1]
    assert regression_inputs == ["patch-v1"]
    assert result["iteration_count"] == 1
    assert result["regression"]["test_status"] == "error"
    assert result["regression"]["per_violation_results"][0]["stdout"] == (
        "Daytona credentials missing"
    )
