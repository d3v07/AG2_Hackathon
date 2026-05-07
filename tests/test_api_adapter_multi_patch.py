"""Tests for backend repair patch passthrough into dashboard data."""
from __future__ import annotations

from api.adapter import report_to_concord_data
from api.store import get_run


def _run_trace() -> dict:
    return {
        "run_id": "RUN-T17",
        "workflow_name": "adapter_fixture",
        "events": [
            {
                "step": 1,
                "agent": "VerifierAgent",
                "type": "agent_turn",
                "content": "I verified the result.",
                "context_delta": {},
                "timestamp": 0.1,
            },
            {
                "step": 2,
                "agent": "ReporterAgent",
                "type": "agent_turn",
                "content": "Final answer",
                "context_delta": {"final_output": {"summary": "done"}},
                "timestamp": 0.2,
            },
        ],
        "final_output": {"summary": "done"},
    }


def _violations() -> list[dict]:
    return [
        {
            "contract_type": "tool",
            "severity": "high",
            "rule": "Claims of verification require tool evidence",
            "expected": "tool_event before verdict",
            "observed": "verdict without tool_event",
            "failed_agent": "VerifierAgent",
            "failed_step": 1,
        },
        {
            "contract_type": "routing",
            "severity": "medium",
            "rule": "Reporter handoff must be gated",
            "expected": "successful Verifier tool event before ReporterAgent",
            "observed": "ReporterAgent ran without gate",
            "failed_agent": "GroupChatManager",
            "failed_step": 2,
        },
    ]


def test_backend_report_patches_passthrough_one_per_violation():
    report = {
        "narrative": "repair plan",
        "patch_code": "# stale scalar patch must not drive dashboard patches",
        "patches": [
            {
                "contract_type": "tool",
                "severity": "high",
                "rule": "Claims of verification require tool evidence",
                "failed_agent": "VerifierAgent",
                "failed_step": 1,
                "repair_patch": "Add verifier tool-event gate",
                "affected_primitive": "OnContextCondition",
                "patch_code": "def require_verifier_tool_event(ctx):\n    return bool(ctx.tool_events)",
                "expected_impact": "blocks unsupported verifier claims",
                "confidence": 0.86,
            },
            {
                "contract_type": "routing",
                "severity": "medium",
                "rule": "Reporter handoff must be gated",
                "failed_agent": "GroupChatManager",
                "failed_step": 2,
                "repair_patch": "Gate reporter handoff on verifier success",
                "affected_primitive": "Handoff",
                "patch_code": "handoff.condition = verifier_tool_event_ok",
                "expected_impact": "prevents premature reporting",
                "confidence": 0.82,
            },
        ],
        "regression_test_status": "passed",
        "approval_status": "approved",
    }

    data = report_to_concord_data(report, _run_trace(), _violations(), sandbox_id="dt-test")

    assert [p["id"] for p in data["patches"]] == ["P-001", "P-002"]
    assert [p["violation"] for p in data["patches"]] == ["V-001", "V-002"]
    assert [p["primitive"] for p in data["patches"]] == ["OnContextCondition", "Handoff"]
    assert [p["target"] for p in data["patches"]] == ["VerifierAgent", "GroupChatManager"]
    assert [p["title"] for p in data["patches"]] == [
        "Add verifier tool-event gate",
        "Gate reporter handoff on verifier success",
    ]
    assert data["patches"][0]["added"] == [
        "def require_verifier_tool_event(ctx):",
        "    return bool(ctx.tool_events)",
    ]
    assert data["patches"][1]["added"] == ["handoff.condition = verifier_tool_event_ok"]
    assert data["patches"][0]["expected_impact"] == "blocks unsupported verifier claims"
    assert data["patches"][1]["confidence"] == 0.82
    assert data["report"]["patches_applied"] == [
        "P-001  OnContextCondition     VerifierAgent",
        "P-002  Handoff                GroupChatManager",
    ]


def test_adapter_keeps_scalar_patch_fallback_when_native_patches_absent():
    report = {
        "narrative": "legacy repair",
        "patch_code": "legacy_patch()",
        "regression_test_status": "passed",
        "approval_status": "approved",
    }

    data = report_to_concord_data(report, _run_trace(), _violations(), sandbox_id="dt-test")

    assert len(data["patches"]) == 2
    assert data["patches"][0]["added"] == ["legacy_patch()"]
    assert data["patches"][1]["added"] == []


def test_seeded_dashboard_fixture_still_serves_patch_shape():
    run = get_run("RUN-041")

    assert run["run"]["id"] == "RUN-041"
    assert len(run["patches"]) == 4
    for patch in run["patches"]:
        assert patch["id"].startswith("P-")
        assert patch["violation"].startswith("V-")
        assert patch["primitive"]
        assert patch["target"]
        assert patch["title"]
        assert isinstance(patch["removed"], list)
        assert patch["added"]
