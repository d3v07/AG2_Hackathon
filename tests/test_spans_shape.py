"""Sprint 15 #72 — span data contract tests (xfail until #74 implements spans block).

Defines the 16-field shape and 10 allowed kinds for `CONCORD_DATA.spans[]`.
Sprint 15 #74 lands `_build_spans_block` in `api/adapter.py`; until then
these tests xfail with a clear reason. Once #74 ships and these tests turn
green, remove the xfail markers (or set strict=True).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REQUIRED_SPAN_FIELDS = {
    "trace_id",
    "span_id",
    "parent_span_id",
    "name",
    "kind",
    "agent",
    "tool",
    "status",
    "start_time",
    "end_time",
    "duration_ms",
    "attributes",
    "input",
    "output",
    "error",
    "contract_refs",
}

ALLOWED_SPAN_KINDS = {
    "workflow",
    "agent",
    "tool",
    "handoff",
    "guardrail",
    "human_gate",
    "action",
    "contract_check",
    "repair",
    "regression",
}


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
            "name": "SpansShapeWorkflow",
            "owner": "d3v07",
            "declared_topology": {"entry": "ResearcherAgent", "edges": []},
            "agents": [{"name": "ResearcherAgent"}],
            "tools": [],
            "contracts": [
                {
                    "id": "C-EVD",
                    "type": "evidence",
                    "rule": "verified_sources_count must be > 0",
                }
            ],
        },
    )
    assert response.status_code == 200
    return response.json()["workflow_id"]


def _submit_with_synthetic_spans(
    client: TestClient,
    workflow_id: str,
    clean_trace_raw: dict,
) -> dict:
    """Submit a raw_trace with a synthetic spans[] field stamped on it."""
    raw_trace = dict(clean_trace_raw)
    raw_trace["spans"] = [
        {
            "trace_id": "tr_001",
            "span_id": "sp_root",
            "parent_span_id": None,
            "name": "concord.workflow",
            "kind": "workflow",
            "agent": None,
            "tool": None,
            "status": "ok",
            "start_time": 0.0,
            "end_time": 2.5,
            "duration_ms": 2500,
            "attributes": {"workflow.name": "LiteratureReviewAssistant"},
            "input": {},
            "output": {},
            "error": None,
            "contract_refs": [],
        },
        {
            "trace_id": "tr_001",
            "span_id": "sp_researcher",
            "parent_span_id": "sp_root",
            "name": "concord.agent.ResearcherAgent",
            "kind": "agent",
            "agent": "ResearcherAgent",
            "tool": None,
            "status": "ok",
            "start_time": 0.1,
            "end_time": 0.5,
            "duration_ms": 400,
            "attributes": {},
            "input": {},
            "output": {},
            "error": None,
            "contract_refs": [],
        },
    ]
    submitted = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": raw_trace},
    )
    run_id = submitted.json()["run_id"]
    return client.get(f"/api/runs/{run_id}").json()


@pytest.mark.xfail(strict=False, reason="spans block lands in #74")
def test_spans_is_a_list(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    data = _submit_with_synthetic_spans(client, workflow_id, clean_trace_raw)

    assert isinstance(data.get("spans"), list)
    assert len(data["spans"]) >= 1


@pytest.mark.xfail(strict=False, reason="spans block lands in #74")
def test_every_span_has_16_required_fields(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    data = _submit_with_synthetic_spans(client, workflow_id, clean_trace_raw)

    for span in data["spans"]:
        missing = REQUIRED_SPAN_FIELDS - set(span.keys())
        assert not missing, f"Span {span.get('span_id')!r} missing fields: {missing}"


@pytest.mark.xfail(strict=False, reason="spans block lands in #74")
def test_kind_is_in_allowed_set(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    data = _submit_with_synthetic_spans(client, workflow_id, clean_trace_raw)

    for span in data["spans"]:
        assert span["kind"] in ALLOWED_SPAN_KINDS, (
            f"Span {span.get('span_id')!r} has invalid kind {span['kind']!r}"
        )


@pytest.mark.xfail(strict=False, reason="spans block lands in #74")
def test_parent_references_resolve(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    data = _submit_with_synthetic_spans(client, workflow_id, clean_trace_raw)

    span_ids = {s["span_id"] for s in data["spans"]}
    for span in data["spans"]:
        parent = span["parent_span_id"]
        if parent is not None:
            assert parent in span_ids, (
                f"Span {span['span_id']!r} references nonexistent parent {parent!r}"
            )


@pytest.mark.xfail(strict=False, reason="spans block lands in #74")
def test_child_timestamps_within_parent(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    data = _submit_with_synthetic_spans(client, workflow_id, clean_trace_raw)

    by_id = {s["span_id"]: s for s in data["spans"]}
    for span in data["spans"]:
        parent_id = span["parent_span_id"]
        if parent_id is None:
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        assert span["start_time"] >= parent["start_time"], (
            f"Span {span['span_id']} starts before parent {parent_id}"
        )
        assert span["end_time"] <= parent["end_time"], (
            f"Span {span['span_id']} ends after parent {parent_id}"
        )
