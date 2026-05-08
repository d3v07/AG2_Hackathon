"""Sprint 15 #72 — violation-to-span linking contract test (xfail until #74/#75).

Each violation in `data["violations"]` must carry a `span_id` field once
spans are wired through (#74 + #75). The referenced span_id must exist in
`data["spans"]` and the span's `agent` must match the violation's
`failed_agent` when both are present.

For runs without spans (legacy), `span_id` may be `None` or missing —
that's the spans-empty backward-compat case.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _client(tmp_path: Path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'runs.db'}")
    init_db()
    return TestClient(app)


def _workflow_id(client: TestClient) -> str:
    response = client.post(
        "/api/workflows",
        json={
            "name": "SpanViolationLinkWorkflow",
            "owner": "d3v07",
            "declared_topology": {"entry": "ResearcherAgent", "edges": []},
            "agents": [
                {"name": "ResearcherAgent"},
                {"name": "VerifierAgent"},
                {"name": "ReporterAgent"},
                {"name": "ActionAgent"},
            ],
            "tools": [],
            "contracts": [
                {"id": "C-EVD", "type": "evidence", "rule": "verified_sources_count > 0"},
                {"id": "C-TOL", "type": "tool", "rule": "verifier needs tool_call_id"},
                {"id": "C-APR", "type": "approval", "rule": "action requires approval"},
            ],
        },
    )
    assert response.status_code == 200
    return response.json()["workflow_id"]


def _submit_failing_run_with_spans(
    client: TestClient,
    workflow_id: str,
    sample_trace_raw: dict,
) -> dict:
    """Submit a violation-producing trace augmented with a synthetic spans[] field."""
    raw_trace = dict(sample_trace_raw)
    raw_trace["spans"] = [
        {
            "trace_id": "tr_v01",
            "span_id": "sp_root",
            "parent_span_id": None,
            "name": "concord.workflow",
            "kind": "workflow",
            "agent": None,
            "tool": None,
            "status": "ok",
            "start_time": 0.0,
            "end_time": 5.0,
            "duration_ms": 5000,
            "attributes": {},
            "input": {},
            "output": {},
            "error": None,
            "contract_refs": [],
        },
        {
            "trace_id": "tr_v01",
            "span_id": "sp_verifier",
            "parent_span_id": "sp_root",
            "name": "concord.agent.VerifierAgent",
            "kind": "agent",
            "agent": "VerifierAgent",
            "tool": None,
            "status": "error",
            "start_time": 1.0,
            "end_time": 1.5,
            "duration_ms": 500,
            "attributes": {},
            "input": {},
            "output": {},
            "error": {"type": "tool_call_missing"},
            "contract_refs": [],
        },
        {
            "trace_id": "tr_v01",
            "span_id": "sp_reporter",
            "parent_span_id": "sp_root",
            "name": "concord.agent.ReporterAgent",
            "kind": "agent",
            "agent": "ReporterAgent",
            "tool": None,
            "status": "ok",
            "start_time": 2.0,
            "end_time": 3.0,
            "duration_ms": 1000,
            "attributes": {},
            "input": {},
            "output": {},
            "error": None,
            "contract_refs": [],
        },
        {
            "trace_id": "tr_v01",
            "span_id": "sp_action",
            "parent_span_id": "sp_root",
            "name": "concord.agent.ActionAgent",
            "kind": "action",
            "agent": "ActionAgent",
            "tool": None,
            "status": "error",
            "start_time": 3.5,
            "end_time": 4.5,
            "duration_ms": 1000,
            "attributes": {},
            "input": {},
            "output": {},
            "error": {"type": "approval_missing"},
            "contract_refs": [],
        },
    ]
    submitted = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": raw_trace},
    )
    assert submitted.status_code == 202, submitted.text
    run_id = submitted.json()["run_id"]
    fetched = client.get(f"/api/runs/{run_id}")
    assert fetched.status_code == 200, fetched.text
    return fetched.json()


@pytest.mark.xfail(strict=True, reason="violation.span_id stamped in #75; remove this marker once it does")
def test_each_violation_has_span_id_field(tmp_path, sample_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    data = _submit_failing_run_with_spans(client, workflow_id, sample_trace_raw)

    violations = data["violations"]
    assert len(violations) > 0, "sample_trace_raw should produce violations"

    for v in violations:
        assert "span_id" in v, f"Violation {v.get('id')!r} missing span_id field"


@pytest.mark.xfail(strict=True, reason="violation.span_id stamped in #75; remove this marker once it does")
def test_violation_span_id_references_existing_span(tmp_path, sample_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    data = _submit_failing_run_with_spans(client, workflow_id, sample_trace_raw)

    span_ids = {s["span_id"] for s in data["spans"]}
    for v in data["violations"]:
        sid = v.get("span_id")
        if sid is not None:
            assert sid in span_ids, (
                f"Violation {v.get('id')!r} references nonexistent span_id {sid!r}"
            )


@pytest.mark.xfail(strict=True, reason="violation.span_id stamped in #75; remove this marker once it does")
def test_violation_span_agent_matches_failed_agent(tmp_path, sample_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    data = _submit_failing_run_with_spans(client, workflow_id, sample_trace_raw)

    by_id = {s["span_id"]: s for s in data["spans"]}
    for v in data["violations"]:
        sid = v.get("span_id")
        failed_agent = v.get("failed_agent")
        if sid and failed_agent and sid in by_id:
            span_agent = by_id[sid].get("agent")
            if span_agent is not None:
                assert span_agent == failed_agent, (
                    f"Violation {v.get('id')!r} span agent {span_agent!r} "
                    f"does not match failed_agent {failed_agent!r}"
                )
