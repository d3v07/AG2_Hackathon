"""Tests for issue #16 per-violation regression results."""
import asyncio

from shared.models import RunTrace, Violation
from zone_b.agents.regression_test import run_regression_test
from zone_b.agents.reporter import run_reporter


def _v(
    contract_type: str,
    severity: str = "high",
    agent: str = "VerifierAgent",
    step: int = 3,
) -> Violation:
    return Violation(
        contract_type=contract_type,
        severity=severity,
        rule=f"{contract_type} rule",
        expected="EXPECTED: repaired state",
        observed="OBSERVED: broken state",
        failed_agent=agent,
        failed_step=step,
    )


def _violations() -> list[Violation]:
    return [
        _v("evidence"),
        _v("tool"),
        _v("approval", agent="ActionAgent", step=5),
        _v("routing", severity="medium", agent="ReporterAgent", step=4),
    ]


def _trace() -> RunTrace:
    return RunTrace("run_041", "LiteratureReviewAssistant", [], None)


def test_regression_returns_one_result_per_violation(monkeypatch):
    assertions = [
        "evidence contract is satisfied post-repair",
        "tool contract is satisfied post-repair",
        "approval contract is satisfied post-repair",
        "routing contract is satisfied post-repair",
    ]
    monkeypatch.setattr(
        "zone_b.agents.regression_test._ask_llm_for_test",
        lambda *_: {
            "test_name": "test_combined_repair",
            "test_code": "print('PASS')",
            "assertions": assertions,
        },
    )
    monkeypatch.setattr(
        "zone_b.agents.regression_test._run_in_daytona",
        lambda _: (
            "PASS evidence\nPASS tool\nPASS approval\nPASS routing\nPASS",
            "sb-001",
            "pass",
        ),
    )

    result = asyncio.run(run_regression_test("patch", _violations(), _trace()))

    assert result["test_status"] == "pass"
    assert result["per_violation_summary"] == {"pass": 4, "fail": 0, "error": 0}
    assert [r["contract_type"] for r in result["per_violation_results"]] == [
        "evidence",
        "tool",
        "approval",
        "routing",
    ]
    assert [r["test_status"] for r in result["per_violation_results"]] == [
        "pass",
        "pass",
        "pass",
        "pass",
    ]
    assert result["per_violation_results"][0]["assertion"] == assertions[0]
    assert result["per_violation_results"][0]["sandbox_id"] == "sb-001"


def test_regression_fallback_produces_per_violation_pass_results(monkeypatch):
    monkeypatch.setattr(
        "zone_b.agents.regression_test._ask_llm_for_test",
        lambda *_: (_ for _ in ()).throw(RuntimeError("generation failed")),
    )
    monkeypatch.setattr(
        "zone_b.agents.regression_test._run_in_daytona",
        lambda _: (
            "PASS evidence\nPASS tool\nPASS approval\nPASS routing\nPASS",
            "sb-fallback",
            "pass",
        ),
    )

    result = asyncio.run(run_regression_test("patch", _violations(), _trace()))

    assert result["fallback_used"] is True
    assert result["fallback_reason"] == "generation_error"
    assert len(result["assertions"]) == 4
    assert len(result["per_violation_results"]) == 4
    assert all(r["test_status"] == "pass" for r in result["per_violation_results"])
    assert result["per_violation_summary"]["pass"] == 4


def test_reporter_adds_test_status_to_each_violation(monkeypatch):
    monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
    violations = _violations()
    repair = {
        "patches": [
            {
                "contract_type": v.contract_type,
                "severity": v.severity,
                "rule": v.rule,
                "failed_agent": v.failed_agent,
                "failed_step": v.failed_step,
                "repair_patch": f"repair {v.contract_type}",
                "affected_primitive": "Guardrail",
                "patch_code": "# patch",
                "expected_impact": "fixes it",
                "confidence": 0.85,
            }
            for v in violations
        ],
        "repair_patch": "repair evidence",
        "affected_primitive": "Guardrail",
        "patch_code": "# patch",
        "expected_impact": "fixes it",
        "confidence": 0.85,
    }
    regression = {
        "test_status": "pass",
        "per_violation_results": [
            {
                "contract_type": v.contract_type,
                "rule": v.rule,
                "failed_agent": v.failed_agent,
                "failed_step": v.failed_step,
                "test_name": f"test_{v.contract_type}",
                "assertion": f"{v.contract_type} assertion",
                "test_status": "pass",
                "stdout": "PASS",
                "sandbox_id": "sb-001",
            }
            for v in violations
        ],
    }

    result = asyncio.run(run_reporter(
        _trace(),
        violations,
        {
            "failed_agent": "VerifierAgent",
            "failed_step": 3,
            "likely_root_cause": "VerifierAgent broke contract",
        },
        repair,
        regression,
    ))
    report = result["report"]

    assert report["regression_summary"] == {"pass": 4, "fail": 0, "error": 0}
    assert len(report["regression_tests"]) == 4
    assert [v["test_status"] for v in report["violations"]] == [
        "pass",
        "pass",
        "pass",
        "pass",
    ]


def test_reporter_defaults_missing_per_violation_status_to_error(monkeypatch):
    monkeypatch.setattr("zone_b.agents.reporter._ask_llm_for_narrative", lambda _: "x")
    violations = _violations()
    regression = {
        "test_status": "pass",
        "per_violation_results": [
            {
                "contract_type": "evidence",
                "failed_agent": "VerifierAgent",
                "failed_step": 3,
                "test_status": "pass",
            }
        ],
    }

    result = asyncio.run(run_reporter(
        _trace(),
        violations,
        {
            "failed_agent": "VerifierAgent",
            "failed_step": 3,
            "likely_root_cause": "VerifierAgent broke contract",
        },
        {"repair_patch": "repair", "affected_primitive": "Guardrail"},
        regression,
    ))

    assert [v["test_status"] for v in result["report"]["violations"]] == [
        "pass",
        "error",
        "error",
        "error",
    ]
