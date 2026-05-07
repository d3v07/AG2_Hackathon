"""Workflow registration API tests."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'workflows.db'}")
    init_db()
    return TestClient(app)


def _workflow_payload() -> dict:
    return {
        "name": "LiteratureReviewAssistant",
        "owner": "d3v07",
        "declared_topology": {
            "entry": "ResearcherAgent",
            "edges": [{"from": "ResearcherAgent", "to": "VerifierAgent"}],
        },
        "agents": [{"name": "ResearcherAgent"}, {"name": "VerifierAgent"}],
        "tools": [{"name": "tavily_search"}],
        "contracts": [
            {
                "id": "C-EVD",
                "type": "evidence",
                "rule": "verified_sources_count must be > 0",
            }
        ],
    }


def _tenant(name: str, key: str) -> dict[str, str]:
    return {"X-Tenant-ID": name, "X-Concord-API-Key": key}


def test_create_list_and_fetch_workflow(tmp_path):
    client = _client(tmp_path)

    created = client.post("/api/workflows", json=_workflow_payload())
    assert created.status_code == 200
    workflow_id = created.json()["workflow_id"]

    listed = client.get("/api/workflows")
    assert listed.status_code == 200
    assert workflow_id in [w["workflow_id"] for w in listed.json()["workflows"]]

    fetched = client.get(f"/api/workflows/{workflow_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "LiteratureReviewAssistant"
    assert fetched.json()["contracts"][0]["id"] == "C-EVD"


def test_invalid_contract_schema_returns_400(tmp_path):
    client = _client(tmp_path)
    payload = _workflow_payload()
    payload["contracts"] = [{"id": "C-BAD", "type": "evidence"}]

    response = client.post("/api/workflows", json=payload)

    assert response.status_code == 400
    assert "contracts[0]" in response.json()["detail"]
    assert "rule" in response.json()["detail"]


def test_workflow_persists_across_database_reinitialization(tmp_path):
    from api.db import configure_database, init_db

    db_url = f"sqlite:///{tmp_path / 'restart.db'}"
    configure_database(db_url)
    init_db()

    client = TestClient(__import__("api.index").index.app)
    workflow_id = client.post("/api/workflows", json=_workflow_payload()).json()["workflow_id"]

    configure_database(db_url)
    init_db()

    restarted_client = TestClient(__import__("api.index").index.app)
    fetched = restarted_client.get(f"/api/workflows/{workflow_id}")
    assert fetched.status_code == 200
    assert fetched.json()["workflow_id"] == workflow_id


def test_workflow_routes_are_tenant_isolated_with_same_workflow_id(tmp_path, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv(
        "CONCORD_TENANT_KEYS",
        '{"tenant-a": "key-a", "tenant-b": "key-b"}',
    )

    class FixedUUID:
        hex = "abc1234500000000"

    monkeypatch.setattr("api.store.uuid.uuid4", lambda: FixedUUID())
    tenant_a_payload = {**_workflow_payload(), "name": "TenantAWorkflow"}
    tenant_b_payload = {**_workflow_payload(), "name": "TenantBWorkflow"}

    created_a = client.post("/api/workflows", headers=_tenant("tenant-a", "key-a"), json=tenant_a_payload)
    created_b = client.post("/api/workflows", headers=_tenant("tenant-b", "key-b"), json=tenant_b_payload)

    assert created_a.status_code == 200
    assert created_b.status_code == 200
    assert created_a.json()["workflow_id"] == created_b.json()["workflow_id"]
    workflow_id = created_a.json()["workflow_id"]

    fetched_a = client.get(f"/api/workflows/{workflow_id}", headers=_tenant("tenant-a", "key-a"))
    fetched_b = client.get(f"/api/workflows/{workflow_id}", headers=_tenant("tenant-b", "key-b"))
    default_tenant = client.get(f"/api/workflows/{workflow_id}")
    listed_a = client.get("/api/workflows", headers=_tenant("tenant-a", "key-a"))
    listed_b = client.get("/api/workflows", headers=_tenant("tenant-b", "key-b"))

    assert fetched_a.json()["name"] == "TenantAWorkflow"
    assert fetched_b.json()["name"] == "TenantBWorkflow"
    assert default_tenant.status_code == 404
    assert [workflow["name"] for workflow in listed_a.json()["workflows"]] == ["TenantAWorkflow"]
    assert [workflow["name"] for workflow in listed_b.json()["workflows"]] == ["TenantBWorkflow"]


def test_non_local_tenant_requires_configured_key(tmp_path, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv("CONCORD_TENANT_KEYS", '{"tenant-a": "key-a"}')

    missing_key = client.get("/api/workflows", headers={"X-Tenant-ID": "tenant-a"})
    wrong_key = client.get(
        "/api/workflows",
        headers={"X-Tenant-ID": "tenant-a", "X-Concord-API-Key": "wrong"},
    )

    assert missing_key.status_code == 401
    assert wrong_key.status_code == 401
