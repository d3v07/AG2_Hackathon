"""Run submission API tests."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'runs.db'}")
    init_db()
    return TestClient(app)


def _workflow_id(client: TestClient) -> str:
    response = client.post(
        "/api/workflows",
        json={
            "name": "CleanWorkflow",
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


def _tenant(tenant_id: str, key: str) -> dict[str, str]:
    return {"X-Tenant-ID": tenant_id, "X-Concord-API-Key": key}


def _workflow_id_for_tenant(client: TestClient, tenant_id: str, key: str, name: str) -> str:
    response = client.post(
        "/api/workflows",
        headers=_tenant(tenant_id, key),
        json={
            "name": name,
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


def test_submit_raw_trace_completes_with_report(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    submitted = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    )

    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]
    assert submitted.json()["status"] == "queued"

    fetched = client.get(f"/api/runs/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "completed"
    assert fetched.json()["run"]["id"] == run_id
    assert fetched.json()["stats"]["violations"] == 0


def test_run_status_polling_endpoint(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    run_id = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    ).json()["run_id"]

    response = client.get(f"/api/runs/{run_id}/status")

    assert response.status_code == 200
    assert response.json()["run_id"] == run_id
    assert response.json()["status"] == "completed"


def test_run_records_status_transition_history(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    run_id = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    ).json()["run_id"]

    status = client.get(f"/api/runs/{run_id}/status").json()
    assert status["status_history"] == ["queued", "analyzing", "completed"]


def test_approval_preserves_status_transition_history(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    run_id = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    ).json()["run_id"]

    response = client.post(f"/api/runs/{run_id}/approval", json={"decision": "approved"})

    assert response.status_code == 200
    status = client.get(f"/api/runs/{run_id}/status").json()
    assert status["status_history"] == ["queued", "analyzing", "completed"]


def test_submit_run_rejects_unknown_workflow(tmp_path, clean_trace_raw):
    client = _client(tmp_path)

    response = client.post(
        "/api/runs",
        json={"workflow_id": "missing", "raw_trace": clean_trace_raw},
    )

    assert response.status_code == 404
    assert "workflow" in response.json()["detail"].lower()


def test_failed_raw_trace_sets_failed_status_with_error(tmp_path):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    submitted = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": {"events": "not-a-list"}},
    )
    run_id = submitted.json()["run_id"]

    status = client.get(f"/api/runs/{run_id}/status").json()
    assert status["status"] == "failed"
    assert status["error"]


def test_task_spec_submission_is_rejected_until_zone_a_runtime_is_wired(tmp_path):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow_id,
            "task_spec": {
                "task": "research multi-agent reliability",
                "research_question": "What makes multi-agent systems reliable?",
            },
        },
    )

    assert response.status_code == 400
    assert "task_spec" in response.json()["detail"]


def test_approval_on_queued_run_returns_conflict_not_500(tmp_path, clean_trace_raw):
    from api.store import create_run

    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    run = create_run(workflow_id=workflow_id, raw_trace=clean_trace_raw)

    fetched = client.get(f"/api/runs/{run['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "queued"
    assert "report" in fetched.json()

    response = client.post(
        f"/api/runs/{run['run_id']}/approval",
        json={"decision": "approved"},
    )

    assert response.status_code == 409
    assert "completed" in response.json()["detail"]


def test_jsonp_run_payload_escapes_javascript_sensitive_characters(tmp_path):
    from api.store import put_run

    client = _client(tmp_path)
    put_run(
        "RUN-JS",
        {
            "run": {"id": "RUN-JS", "workflow": "JS"},
            "patches": [],
            "violations": [],
            "report": {
                "summary": "line\u2028break<script>",
                "approval": {"status": "PENDING_OPERATOR"},
            },
        },
    )

    response = client.get("/api/runs/RUN-JS.js")

    assert response.status_code == 200
    assert "\\u2028" in response.text
    assert "\\u003cscript>" in response.text
    assert "line\u2028break<script>" not in response.text


def test_jsonp_run_payload_supports_script_loader_stream_token_after_auth(tmp_path):
    from api.auth import create_api_key
    from api.store import put_run

    client = _client(tmp_path)
    api_key = create_api_key(tenant_id="local", name="local browser")["api_key"]
    put_run(
        "RUN-JS",
        {
            "run": {"id": "RUN-JS", "workflow": "JS"},
            "patches": [],
            "violations": [],
            "report": {"approval": {"status": "PENDING_OPERATOR"}},
        },
    )

    denied = client.get("/api/runs/RUN-JS.js")
    token = client.post(
        "/api/runs/RUN-JS/events/token",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    allowed = client.get(f"/api/runs/RUN-JS.js?stream_token={token.json()['stream_token']}")

    assert denied.status_code == 401
    assert token.status_code == 200
    assert allowed.status_code == 200
    assert "window.CONCORD_DATA" in allowed.text


def test_run_routes_are_tenant_isolated_with_same_run_id(tmp_path, clean_trace_raw, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv(
        "CONCORD_TENANT_KEYS",
        '{"tenant-a": "key-a", "tenant-b": "key-b"}',
    )
    workflow_a = _workflow_id_for_tenant(client, "tenant-a", "key-a", "TenantAWorkflow")
    workflow_b = _workflow_id_for_tenant(client, "tenant-b", "key-b", "TenantBWorkflow")

    class FixedUUID:
        hex = "deadbeef00000000"

    trace_a = dict(clean_trace_raw)
    trace_a["workflow_name"] = "TenantAWorkflow"
    trace_b = dict(clean_trace_raw)
    trace_b["workflow_name"] = "TenantBWorkflow"
    monkeypatch.setattr("api.store.uuid.uuid4", lambda: FixedUUID())

    submitted_a = client.post(
        "/api/runs",
        headers=_tenant("tenant-a", "key-a"),
        json={"workflow_id": workflow_a, "raw_trace": trace_a},
    )
    submitted_b = client.post(
        "/api/runs",
        headers=_tenant("tenant-b", "key-b"),
        json={"workflow_id": workflow_b, "raw_trace": trace_b},
    )

    assert submitted_a.status_code == 202
    assert submitted_b.status_code == 202
    assert submitted_a.json()["run_id"] == submitted_b.json()["run_id"]
    run_id = submitted_a.json()["run_id"]

    fetched_a = client.get(f"/api/runs/{run_id}", headers=_tenant("tenant-a", "key-a"))
    fetched_b = client.get(f"/api/runs/{run_id}", headers=_tenant("tenant-b", "key-b"))
    fetched_default = client.get(f"/api/runs/{run_id}")
    status_a = client.get(f"/api/runs/{run_id}/status", headers=_tenant("tenant-a", "key-a"))
    status_b = client.get(f"/api/runs/{run_id}/status", headers=_tenant("tenant-b", "key-b"))
    listed_a = client.get("/api/runs", headers=_tenant("tenant-a", "key-a"))
    listed_b = client.get("/api/runs", headers=_tenant("tenant-b", "key-b"))

    assert fetched_a.json()["run"]["workflow"] == "TENANTAWORKFLOW"
    assert fetched_b.json()["run"]["workflow"] == "TENANTBWORKFLOW"
    assert fetched_default.status_code == 404
    assert status_a.json()["status"] == "completed"
    assert status_b.json()["status"] == "completed"
    assert listed_a.json()["run_ids"] == [run_id]
    assert listed_b.json()["run_ids"] == [run_id]

    approved_a = client.post(
        f"/api/runs/{run_id}/approval",
        headers=_tenant("tenant-a", "key-a"),
        json={"decision": "rejected"},
    )

    assert approved_a.status_code == 200
    assert approved_a.json()["approval"]["status"] == "REJECTED"
    assert client.get(f"/api/runs/{run_id}", headers=_tenant("tenant-b", "key-b")).json()[
        "report"
    ]["approval"]["status"] == "APPROVED"


def test_startup_marks_interrupted_runs_failed_after_restart(tmp_path, clean_trace_raw):
    from api.db import configure_database, init_db
    from api.index import app
    from api.store import create_run, create_workflow, get_run_status, set_run_status

    db_url = f"sqlite:///{tmp_path / 'restart-runs.db'}"
    configure_database(db_url)
    init_db()
    workflow = create_workflow(
        {
            "name": "RestartWorkflow",
            "declared_topology": {},
            "agents": [],
            "tools": [],
            "contracts": [],
        }
    )
    run = create_run(workflow_id=workflow["workflow_id"], raw_trace=clean_trace_raw)
    set_run_status(run["run_id"], "analyzing")
    assert get_run_status(run["run_id"])["status"] == "analyzing"

    configure_database(db_url)
    with TestClient(app) as client:
        status = client.get(f"/api/runs/{run['run_id']}/status").json()

    assert status["status"] == "failed"
    assert status["status_history"] == ["queued", "analyzing", "failed"]
    assert "interrupted" in status["error"]
