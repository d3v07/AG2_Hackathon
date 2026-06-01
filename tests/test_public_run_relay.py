"""Public same-origin run relay tests."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'public-runs.db'}")
    init_db()
    return TestClient(app)


def _workflow_payload() -> dict:
    return {
        "name": "PublicWorkflow",
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
    }


def _task_payload(workflow_id: str) -> dict:
    return {
        "workflow_id": workflow_id,
        "task_spec": {
            "task": "Create a reliability memo.",
            "research_question": "Do multi-agent systems improve reliability?",
        },
    }


def test_public_run_relay_is_disabled_by_default(tmp_path):
    client = _client(tmp_path)

    response = client.post("/api/public/runs", json=_task_payload("WF-MISSING"))

    assert response.status_code == 403
    assert response.json()["detail"] == "public run submission is disabled"


def test_public_run_relay_submits_task_spec_without_browser_api_key(tmp_path, monkeypatch):
    from api.store import create_workflow

    client = _client(tmp_path)
    monkeypatch.setenv("CONCORD_PUBLIC_RUNS_ENABLED", "1")
    monkeypatch.setenv("CONCORD_PUBLIC_TENANT_ID", "public-tenant")
    workflow_id = create_workflow(_workflow_payload(), tenant_id="public-tenant")["workflow_id"]
    processed: list[tuple[str, str]] = []

    def fake_process_run(run_id: str, tenant_id: str) -> None:
        processed.append((run_id, tenant_id))

    monkeypatch.setattr("api.background.process_run", fake_process_run)

    response = client.post("/api/public/runs", json=_task_payload(workflow_id))

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert processed == [(response.json()["run_id"], "public-tenant")]


def test_public_run_relay_rejects_raw_trace_submission(tmp_path, clean_trace_raw, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv("CONCORD_PUBLIC_RUNS_ENABLED", "1")

    response = client.post(
        "/api/public/runs",
        json={"workflow_id": "WF-RAW", "raw_trace": clean_trace_raw},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "public run submission accepts task_spec only"
