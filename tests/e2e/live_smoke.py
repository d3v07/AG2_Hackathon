"""Live end-to-end smoke against a hosted Concord backend.

Exercises the full task_spec -> AG2 swarm -> Zone B contract checking ->
Daytona regression -> forensic CONCORD_DATA -> history -> approval flow.

Skipped unless OPENROUTER_API_KEY is set (the live-mode gate). The test
hits a real backend at CONCORD_API_BASE, registers the canonical
Literature Review topology with 5 deterministic contracts, submits a
task_spec run with mode=live, polls until completion, validates that the
demo produced violations, patches, validation state, and history, then
approves the run.

Run locally:
    OPENROUTER_API_KEY=... TAVILY_API_KEY=... DAYTONA_API_KEY=... \
        pytest tests/e2e/live_smoke.py -m live_smoke -v

Run in CI: dispatched manually via .github/workflows/live-smoke.yml.
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx
import pytest

DEFAULT_API_BASE = "http://localhost:8000"
POLL_INTERVAL_SECONDS = 2.0
RUN_TIMEOUT_SECONDS = 180.0
HTTP_TIMEOUT_SECONDS = 30.0
TERMINAL_STATUSES = {"completed", "failed"}
VALIDATION_STATES = {
    "passed",
    "failed",
    "skipped",
    "unavailable",
    "credential_failure",
    "execution_error",
}


pytestmark = pytest.mark.live_smoke


def _require_live_mode() -> None:
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip(
            "OPENROUTER_API_KEY is unset; live smoke requires real LLM credentials. "
            "Set OPENROUTER_API_KEY (and TAVILY_API_KEY, DAYTONA_API_KEY) to run.",
        )


def _auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("CONCORD_API_KEY")
    if api_key:
        headers["X-Concord-API-Key"] = api_key
    return headers


def _canonical_workflow_payload() -> dict[str, Any]:
    return {
        "name": "LiteratureReviewAssistant-LiveSmoke",
        "owner": "live-smoke",
        "declared_topology": {
            "entry": "ResearcherAgent",
            "edges": [
                {"from": "ResearcherAgent", "to": "CriticAgent"},
                {"from": "CriticAgent", "to": "VerifierAgent"},
                {"from": "VerifierAgent", "to": "ReporterAgent"},
                {"from": "ReporterAgent", "to": "HumanGateAgent"},
                {"from": "HumanGateAgent", "to": "ActionAgent"},
            ],
        },
        "agents": [
            {"name": "ResearcherAgent"},
            {"name": "CriticAgent"},
            {"name": "VerifierAgent"},
            {"name": "ReporterAgent"},
            {"name": "HumanGateAgent"},
            {"name": "ActionAgent"},
        ],
        "tools": [{"name": "tavily_search"}],
        "contracts": [
            {
                "id": "C-EVD",
                "type": "evidence",
                "severity": "high",
                "rule": "Reporter may write final_output only when verified_sources_count > 0",
                "failed_agent": "ReporterAgent",
            },
            {
                "id": "C-TOL",
                "type": "tool",
                "severity": "high",
                "rule": "Agents claiming verified/searched/checked must record a tool_call_id",
                "failed_agent": "VerifierAgent",
            },
            {
                "id": "C-RTE",
                "type": "routing",
                "severity": "medium",
                "rule": "ReporterAgent runs after VerifierAgent's successful tool event; ActionAgent requires HumanGate first",
                "failed_agent": "ReporterAgent",
            },
            {
                "id": "C-APR",
                "type": "approval",
                "severity": "high",
                "rule": "ActionAgent requires approval_status == approved",
                "failed_agent": "ActionAgent",
            },
            {
                "id": "C-SCH",
                "type": "schema",
                "severity": "medium",
                "rule": "final_output must include summary, claims[], citations[], risks[], next_steps[]",
                "failed_agent": "ReporterAgent",
            },
        ],
    }


def _task_spec_payload() -> dict[str, Any]:
    return {
        "task": (
            "Produce a concise literature review on whether multi-agent systems improve "
            "reliability in research workflows."
        ),
        "research_question": "Do multi-agent systems improve reliability in research workflows?",
        "mode": "live",
    }


def _register_workflow(client: httpx.Client, base: str) -> str:
    response = client.post(
        f"{base}/api/workflows",
        json=_canonical_workflow_payload(),
        headers=_auth_headers(),
    )
    assert response.status_code == 200, f"workflow registration failed: {response.status_code} {response.text}"
    workflow_id = response.json()["workflow_id"]
    assert workflow_id, "workflow_id missing from create response"
    return workflow_id


def _submit_run(client: httpx.Client, base: str, workflow_id: str) -> str:
    body = {
        "workflow_id": workflow_id,
        "task_spec": _task_spec_payload(),
    }
    response = client.post(f"{base}/api/runs", json=body, headers=_auth_headers())
    assert response.status_code in (200, 202), (
        f"run submission failed: {response.status_code} {response.text}"
    )
    run_id = response.json()["run_id"]
    assert run_id, "run_id missing from submit response"
    return run_id


def _poll_until_terminal(client: httpx.Client, base: str, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    last_status: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = client.get(
            f"{base}/api/runs/{run_id}/status",
            headers=_auth_headers(),
        )
        assert response.status_code == 200, (
            f"status poll failed: {response.status_code} {response.text}"
        )
        last_status = response.json()
        if last_status.get("status") in TERMINAL_STATUSES:
            return last_status
        time.sleep(POLL_INTERVAL_SECONDS)
    pytest.fail(
        f"run {run_id} did not reach terminal state within {RUN_TIMEOUT_SECONDS}s; "
        f"last status: {last_status}",
    )


def _fetch_run(client: httpx.Client, base: str, run_id: str) -> dict[str, Any]:
    response = client.get(f"{base}/api/runs/{run_id}", headers=_auth_headers())
    assert response.status_code == 200, (
        f"run fetch failed: {response.status_code} {response.text}"
    )
    return response.json()


def _approve_run(client: httpx.Client, base: str, run_id: str) -> dict[str, Any]:
    response = client.post(
        f"{base}/api/runs/{run_id}/approval",
        json={"decision": "approved", "operator": "live-smoke", "comments": "smoke test"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200, (
        f"approval failed: {response.status_code} {response.text}"
    )
    return response.json()


def _assert_history_contains(client: httpx.Client, base: str, run_id: str) -> None:
    response = client.get(f"{base}/api/runs", headers=_auth_headers())
    assert response.status_code == 200, (
        f"run history fetch failed: {response.status_code} {response.text}"
    )
    assert run_id in response.json().get("run_ids", []), (
        f"run {run_id} missing from history: {response.text}"
    )


def _assert_concord_data_shape(payload: dict[str, Any]) -> None:
    spans = payload.get("spans")
    assert isinstance(spans, list) and spans, (
        "CONCORD_DATA.spans must be a non-empty list (Sprint 15 #74 contract)"
    )

    violations = payload.get("violations") or []
    assert violations, "demo run must produce at least one contract violation"
    for index, violation in enumerate(violations):
        assert violation.get("span_id"), (
            f"violations[{index}] missing span_id (Sprint 15 #75 contract); got {violation}"
        )

    patches = payload.get("patches") or []
    assert patches, "demo run must produce at least one repair patch"
    test_block = payload.get("test") or {}
    report = payload.get("report") or {}
    validation_state = test_block.get("validation_state") or report.get("validation_state")
    assert validation_state in VALIDATION_STATES, (
        f"demo run missing honest validation state; got {validation_state!r}"
    )
    assertions = test_block.get("assertions") or []
    assert len(assertions) >= len(patches), (
        f"each patch must have a corresponding regression assertion; "
        f"patches={len(patches)} assertions={len(assertions)}"
    )
    for index, patch in enumerate(patches):
        patch_violation = patch.get("violation")
        assert patch_violation, f"patches[{index}] missing violation reference"
        assertion = assertions[index]
        assert assertion.get("status") in {"PASS", "FAIL"}, (
            f"regression assertions[{index}] missing status"
        )


def test_live_smoke_full_flow() -> None:
    """Full task_spec -> swarm -> contracts -> regression -> approval flow."""
    _require_live_mode()
    base = os.getenv("CONCORD_API_BASE", DEFAULT_API_BASE).rstrip("/")

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        workflow_id = _register_workflow(client, base)
        run_id = _submit_run(client, base, workflow_id)

        terminal = _poll_until_terminal(client, base, run_id)
        assert terminal.get("status") == "completed", (
            f"run {run_id} did not complete: {terminal}"
        )

        run_payload = _fetch_run(client, base, run_id)
        _assert_concord_data_shape(run_payload)
        _assert_history_contains(client, base, run_id)

        _approve_run(client, base, run_id)
        approved_payload = _fetch_run(client, base, run_id)
        approved_report = approved_payload.get("report") or approved_payload
        approval_block = (approved_report.get("report") or {}).get("approval") or {}
        assert approval_block.get("status") == "APPROVED", (
            f"approval state did not update to APPROVED; got {approval_block}"
        )
