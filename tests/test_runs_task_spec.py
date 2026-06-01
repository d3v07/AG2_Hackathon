"""Sprint 13 #67 — task_spec API wiring tests."""
from __future__ import annotations

import json
from pathlib import Path

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
            "name": "TaskSpecWorkflow",
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
    assert response.status_code == 200, response.text
    return response.json()["workflow_id"]


def test_task_spec_stub_mode_completes_run(tmp_path):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    submitted = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "task_spec": {
                "task": "Survey reliability patterns in multi-agent systems",
                "research_question": "What architectural patterns improve MAS reliability?",
                "mode": "stub",
            },
        },
    )
    assert submitted.status_code == 202, submitted.text
    run_id = submitted.json()["run_id"]
    assert submitted.json()["status"] == "queued"

    fetched = client.get(f"/api/runs/{run_id}")
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()
    assert data["status"] == "completed"
    assert data["run"]["id"] == run_id
    # Stub mode produces a clean trace -> zero violations
    assert data["stats"]["violations"] == 0


def test_task_spec_default_mode_is_live(tmp_path, monkeypatch, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    seen: dict[str, str] = {}

    async def fake_run_swarm(**kwargs):
        seen["mode"] = kwargs["mode"]
        output_path = kwargs["output_path"]
        payload = dict(clean_trace_raw)
        payload["run_id"] = kwargs["run_id"]
        output_path.write_text(json.dumps(payload))
        return {"trace_path": str(output_path)}

    monkeypatch.setattr("api.background.run_swarm", fake_run_swarm)

    submitted = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "task_spec": {
                "task": "t",
                "research_question": "rq",
            },
        },
    )
    assert submitted.status_code == 202, submitted.text
    run_id = submitted.json()["run_id"]
    data = client.get(f"/api/runs/{run_id}").json()
    assert data["status"] == "completed"
    assert seen["mode"] == "live"


def test_task_spec_unknown_workflow_returns_404(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/api/runs",
        json={
            "workflow_id": "WF-does-not-exist",
            "task_spec": {
                "task": "t",
                "research_question": "rq",
                "mode": "stub",
            },
        },
    )
    assert response.status_code == 404
    assert "workflow" in response.json()["detail"].lower()


def test_task_spec_rejects_empty_task(tmp_path):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "task_spec": {
                "task": "",
                "research_question": "rq",
                "mode": "stub",
            },
        },
    )
    assert response.status_code == 422


def test_task_spec_rejects_empty_research_question(tmp_path):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "task_spec": {
                "task": "t",
                "research_question": "",
                "mode": "stub",
            },
        },
    )
    assert response.status_code == 422


def test_task_spec_rejects_unknown_mode(tmp_path):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "task_spec": {
                "task": "t",
                "research_question": "rq",
                "mode": "bogus",
            },
        },
    )
    assert response.status_code == 422


def test_both_raw_trace_and_task_spec_returns_422(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "raw_trace": clean_trace_raw,
            "task_spec": {
                "task": "t",
                "research_question": "rq",
                "mode": "stub",
            },
        },
    )
    assert response.status_code == 422


def test_neither_raw_trace_nor_task_spec_returns_422(tmp_path):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    response = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id},
    )
    assert response.status_code == 422


def test_raw_trace_path_still_works(tmp_path, clean_trace_raw):
    """Sprint 13 #67 must NOT regress the existing raw_trace path."""
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    submitted = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    )
    assert submitted.status_code == 202, submitted.text
    run_id = submitted.json()["run_id"]
    data = client.get(f"/api/runs/{run_id}").json()
    assert data["status"] == "completed"
    assert data["stats"]["violations"] == 0
