"""Tests for backend repair patch passthrough into dashboard data."""
from __future__ import annotations

import json
from pathlib import Path

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
            "failed_agent": "ReporterAgent",
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
        "sandbox_id": "dt-report",
        "regression_duration_ms": 1250,
        "regression_usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        "regression_cost": {
            "daytona_seconds": 1.25,
            "llm_tokens": 12,
            "llm_cost_usd": 0.00006,
            "daytona_cost_usd": 0.00025,
        },
        "regression_summary": {"pass": 2, "fail": 0, "error": 0},
        "regression_tests": [
            {"test_name": "test_tool", "test_status": "pass", "sandbox_id": "dt-report"},
            {"test_name": "test_routing", "test_status": "pass", "sandbox_id": "dt-report"},
        ],
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
    assert data["test"]["sandbox_id"] == "dt-report"
    assert data["test"]["duration_ms"] == 1250
    assert data["cost"] == {
        "daytona_seconds": 1.25,
        "llm_tokens": 12,
        "llm_cost_usd": 0.00006,
        "daytona_cost_usd": 0.00025,
    }
    assert data["report"]["regression_summary"] == {"pass": 2, "fail": 0, "error": 0}
    assert data["report"]["regression_tests"][0]["test_name"] == "test_tool"
    assert data["report"]["usage_summary"] == {
        "prompt_tokens": 8,
        "completion_tokens": 4,
        "total_tokens": 12,
    }
    assert data["report"]["cost_summary"] == data["cost"]


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


def test_adapter_treats_pass_regression_status_as_success():
    report = {
        "narrative": "repair passed",
        "patch_code": "legacy_patch()",
        "regression_test_status": "pass",
        "approval_status": "approved",
    }

    data = report_to_concord_data(report, _run_trace(), _violations(), sandbox_id="dt-test")

    assert [a["status"] for a in data["test"]["assertions"]] == ["PASS", "PASS"]
    assert [line["k"] for line in data["test"]["lines"] if line["k"] in {"pass", "fail"}] == [
        "pass",
        "pass",
    ]


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


def test_adapter_emits_topology_and_routes_for_live_dashboard():
    report = {
        "narrative": "live repair",
        "patch_code": "legacy_patch()",
        "regression_test_status": "passed",
        "approval_status": "approved",
    }

    data = report_to_concord_data(report, _run_trace(), _violations(), sandbox_id="dt-test")

    assert data["topology"]["entry"] == "VRF"
    assert {node["name"] for node in data["topology"]["nodes"]} == {
        "VerifierAgent",
        "ReporterAgent",
    }
    assert {(edge["from"], edge["to"], edge["kind"]) for edge in data["topology"]["edges"]} == {
        ("VRF", "RPT", "handoff"),
    }
    assert [(route["from"], route["to"], route["observed"]) for route in data["routes"]] == [
        ("VRF", "RPT", True),
    ]
    assert data["routes"][0]["contract"] == "C-RTE"
    assert data["routes"][0]["status"] == "skipped_guard"
    assert all(node["name"] not in {"GroupChatManager", "HumanGate"} for node in data["topology"]["nodes"])
    assert all({"id", "from", "to", "declared", "observed", "status"} <= route.keys() for route in data["routes"])


def test_adapter_does_not_leak_fixture_topology_into_custom_live_runs():
    report = {
        "narrative": "custom repair",
        "patch_code": "legacy_patch()",
        "regression_test_status": "passed",
        "approval_status": "approved",
    }
    run_trace = {
        "run_id": "RUN-X",
        "workflow_name": "custom",
        "events": [
            {
                "step": 1,
                "agent": "AlphaAgent",
                "type": "agent_turn",
                "content": "",
                "context_delta": {},
                "handoff_to": "BetaAgent",
                "timestamp": 0.1,
            },
            {
                "step": 2,
                "agent": "BetaAgent",
                "type": "agent_turn",
                "content": "",
                "context_delta": {},
                "timestamp": 0.2,
            },
        ],
        "final_output": None,
    }
    violations = [
        {
            "contract_type": "approval",
            "severity": "high",
            "rule": "approval required",
            "expected": "approved before side effect",
            "observed": "ran without approval",
            "failed_agent": "BetaAgent",
            "failed_step": 2,
        },
    ]

    data = report_to_concord_data(report, run_trace, violations, sandbox_id="dt-test")

    assert {node["name"] for node in data["topology"]["nodes"]} == {"AlphaAgent", "BetaAgent"}
    assert all(
        node["name"] not in {
            "HumanGate",
            "GroupChatManager",
            "ResearcherAgent",
            "CriticAgent",
            "VerifierAgent",
            "ReporterAgent",
            "ActionAgent",
            "tavily_search",
        }
        for node in data["topology"]["nodes"]
    )
    assert all(route["observed"] is True for route in data["routes"])
    assert all(route["status"] != "unexpected" for route in data["routes"])


def test_adapter_derives_sample_trace_topology_without_manager_or_gate():
    report = {
        "narrative": "sample repair",
        "patch_code": "legacy_patch()",
        "regression_test_status": "passed",
        "approval_status": "approved",
    }
    sample_trace_raw = json.loads(Path("zone_b/fixtures/sample_trace.json").read_text())
    violations = [
        {
            "contract_type": "approval",
            "severity": "high",
            "rule": "approval required",
            "expected": "approved before side effect",
            "observed": "ran without approval",
            "failed_agent": "ActionAgent",
            "failed_step": 5,
        },
    ]

    data = report_to_concord_data(report, sample_trace_raw, violations, sandbox_id="dt-test")

    assert {node["name"] for node in data["topology"]["nodes"]} == {
        "ResearcherAgent",
        "tavily_search",
        "CriticAgent",
        "VerifierAgent",
        "ReporterAgent",
        "ActionAgent",
    }
    assert "GroupChatManager" not in {node["name"] for node in data["topology"]["nodes"]}
    assert "HumanGate" not in {node["name"] for node in data["topology"]["nodes"]}
