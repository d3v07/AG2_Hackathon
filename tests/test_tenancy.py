"""Tenant isolation tests for API and store boundaries."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'tenancy.db'}")
    init_db()
    return TestClient(app)


def _key(tenant_id: str) -> str:
    from api.auth import create_api_key

    return create_api_key(tenant_id=tenant_id, name=f"{tenant_id} test")["api_key"]


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _workflow_payload(name: str = "Workflow") -> dict:
    return {
        "name": name,
        "owner": "d3v07",
        "declared_topology": {"entry": "ResearcherAgent", "edges": []},
        "agents": [{"name": "ResearcherAgent"}],
        "tools": [],
        "contracts": [{"id": "C-EVD", "type": "evidence", "rule": "verified_sources_count > 0"}],
    }


def test_workflow_fetch_is_tenant_isolated(tmp_path):
    client = _client(tmp_path)
    tenant_a = _key("tenant-a")
    tenant_b = _key("tenant-b")
    created = client.post(
        "/api/workflows",
        headers=_auth(tenant_a),
        json=_workflow_payload("TenantAWorkflow"),
    )
    assert created.status_code == 200
    workflow_id = created.json()["workflow_id"]

    hidden = client.get(f"/api/workflows/{workflow_id}", headers=_auth(tenant_b))
    visible = client.get(f"/api/workflows/{workflow_id}", headers=_auth(tenant_a))

    assert hidden.status_code == 404
    assert visible.status_code == 200
    assert visible.json()["name"] == "TenantAWorkflow"


def test_run_json_and_jsonp_are_tenant_isolated_for_same_run_id(tmp_path):
    client = _client(tmp_path)
    tenant_a = _key("tenant-a")
    tenant_b = _key("tenant-b")
    from api.store import put_run

    put_run(
        "RUN-SHARED",
        {"run": {"id": "RUN-SHARED", "workflow": "tenant-a-workflow"}, "patches": [], "violations": []},
        tenant_id="tenant-a",
    )
    put_run(
        "RUN-SHARED",
        {"run": {"id": "RUN-SHARED", "workflow": "tenant-b-workflow"}, "patches": [], "violations": []},
        tenant_id="tenant-b",
    )

    run_a = client.get("/api/runs/RUN-SHARED", headers=_auth(tenant_a))
    run_b_js = client.get("/api/runs/RUN-SHARED.js", headers=_auth(tenant_b))

    assert run_a.status_code == 200
    assert run_a.json()["run"]["workflow"] == "tenant-a-workflow"
    assert run_b_js.status_code == 200
    assert "tenant-b-workflow" in run_b_js.text
    assert "tenant-a-workflow" not in run_b_js.text


def test_event_token_minting_is_tenant_scoped(tmp_path):
    client = _client(tmp_path)
    tenant_a = _key("tenant-a")
    tenant_b = _key("tenant-b")
    from api.store import put_run

    put_run(
        "RUN-EVENT",
        {"run": {"id": "RUN-EVENT", "workflow": "tenant-a-workflow"}, "patches": [], "violations": []},
        tenant_id="tenant-a",
    )

    denied = client.post("/api/runs/RUN-EVENT/events/token", headers=_auth(tenant_b))
    granted = client.post("/api/runs/RUN-EVENT/events/token", headers=_auth(tenant_a))

    assert denied.status_code == 404
    assert granted.status_code == 200
    assert granted.json()["stream_token"]


def test_child_rows_are_filtered_by_tenant_for_same_run_id(tmp_path):
    _client(tmp_path)
    from api.store import get_run, put_run

    put_run(
        "RUN-CHILD",
        {
            "run": {"id": "RUN-CHILD", "workflow": "tenant-a-workflow"},
            "patches": [{"id": "P-A", "target": "VerifierAgent"}],
            "violations": [{"id": "V-A", "contract_type": "routing", "failed_agent": "VerifierAgent"}],
            "test": {"assertions": [{"name": "tenant-a assertion", "status": "pass"}]},
        },
        tenant_id="tenant-a",
    )
    put_run(
        "RUN-CHILD",
        {
            "run": {"id": "RUN-CHILD", "workflow": "tenant-b-workflow"},
            "patches": [{"id": "P-B", "target": "ReporterAgent"}],
            "violations": [{"id": "V-B", "contract_type": "approval", "failed_agent": "ActionAgent"}],
            "test": {"assertions": [{"name": "tenant-b assertion", "status": "pass"}]},
        },
        tenant_id="tenant-b",
    )

    run_a = get_run("RUN-CHILD", tenant_id="tenant-a")
    run_b = get_run("RUN-CHILD", tenant_id="tenant-b")

    assert [patch["id"] for patch in run_a["patches"]] == ["P-A"]
    assert [patch["id"] for patch in run_b["patches"]] == ["P-B"]
    assert [violation["id"] for violation in run_a["violations"]] == ["V-A"]
    assert [violation["id"] for violation in run_b["violations"]] == ["V-B"]
    assert run_a["test"]["assertions"][0]["name"] == "tenant-a assertion"
    assert run_b["test"]["assertions"][0]["name"] == "tenant-b assertion"


def test_recover_interrupted_runs_filters_by_tenant(tmp_path):
    _client(tmp_path)
    from api.store import create_run, recover_interrupted_runs

    run_a = create_run(workflow_id="WF-A", raw_trace={"events": []}, tenant_id="tenant-a")["run_id"]
    run_b = create_run(workflow_id="WF-B", raw_trace={"events": []}, tenant_id="tenant-b")["run_id"]

    recovered = recover_interrupted_runs(tenant_id="tenant-a")

    assert recovered == 1
    from api.store import get_run_status

    assert get_run_status(run_a, tenant_id="tenant-a")["status"] == "failed"
    assert get_run_status(run_b, tenant_id="tenant-b")["status"] == "queued"


def test_recover_interrupted_runs_defaults_to_all_tenants(tmp_path):
    _client(tmp_path)
    from api.store import create_run, get_run_status, recover_interrupted_runs

    run_a = create_run(workflow_id="WF-A", raw_trace={"events": []}, tenant_id="tenant-a")["run_id"]
    run_b = create_run(workflow_id="WF-B", raw_trace={"events": []}, tenant_id="tenant-b")["run_id"]

    recovered = recover_interrupted_runs()

    assert recovered == 2
    assert get_run_status(run_a, tenant_id="tenant-a")["status"] == "failed"
    assert get_run_status(run_b, tenant_id="tenant-b")["status"] == "failed"
