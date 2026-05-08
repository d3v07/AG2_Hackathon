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


def test_create_workflow_persists_declared_topology_to_graph(tmp_path, monkeypatch):
    client = _client(tmp_path)
    calls = []

    def record_graph_call(workflow, tenant_id):
        calls.append((workflow, tenant_id))
        return {"enabled": True, "nodes": 1, "edges": 1}

    monkeypatch.setattr("api.store.persist_workflow_topology", record_graph_call)

    created = client.post("/api/workflows", json=_workflow_payload())

    assert created.status_code == 200
    assert len(calls) == 1
    assert calls[0][0]["workflow_id"] == created.json()["workflow_id"]
    assert calls[0][0]["declared_topology"]["edges"] == [
        {"from": "ResearcherAgent", "to": "VerifierAgent"}
    ]
    assert calls[0][1] == "local"


def test_create_workflow_survives_graph_persistence_failure(tmp_path, monkeypatch):
    client = _client(tmp_path)

    def fail_graph_call(_workflow, _tenant_id):
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr("api.store.persist_workflow_topology", fail_graph_call)

    created = client.post("/api/workflows", json=_workflow_payload())

    assert created.status_code == 200
    workflow_id = created.json()["workflow_id"]
    fetched = client.get(f"/api/workflows/{workflow_id}")
    assert fetched.status_code == 200
    assert fetched.json()["workflow_id"] == workflow_id


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


def test_get_workflow_recurrences_returns_empty_list_for_clean_workflow(tmp_path):
    client = _client(tmp_path)
    workflow_id = client.post("/api/workflows", json=_workflow_payload()).json()["workflow_id"]

    response = client.get(f"/api/workflows/{workflow_id}/recurrences")

    assert response.status_code == 200
    assert response.json() == {"workflow_id": workflow_id, "recurrences": []}


def test_get_workflow_recurrences_groups_same_violation_across_runs(tmp_path):
    from api.store import put_run

    client = _client(tmp_path)
    workflow_id = client.post("/api/workflows", json=_workflow_payload()).json()["workflow_id"]
    for index in range(5):
        put_run(
            f"RUN-REC-{index}",
            {
                "run": {"id": f"RUN-REC-{index}", "workflow": "LiteratureReviewAssistant"},
                "patches": [],
                "violations": [
                    {
                        "contract_type": "routing",
                        "severity": "MED",
                        "rule": "Reporter handoff must be gated",
                        "failed_agent": "GroupChatManager",
                        "failed_step": 10,
                    }
                ],
                "report": {"approval": {"status": "PENDING_OPERATOR"}},
            },
            workflow_id=workflow_id,
            status="completed",
        )

    response = client.get(f"/api/workflows/{workflow_id}/recurrences")

    assert response.status_code == 200
    rows = response.json()["recurrences"]
    assert len(rows) == 1
    assert rows[0]["contract_type"] == "routing"
    assert rows[0]["failed_agent"] == "GroupChatManager"
    assert rows[0]["rule"] == "Reporter handoff must be gated"
    assert rows[0]["count"] == 5
    assert rows[0]["sample_run_ids"] == [
        "RUN-REC-0",
        "RUN-REC-1",
        "RUN-REC-2",
        "RUN-REC-3",
        "RUN-REC-4",
    ]
    assert rows[0]["contract"] == "C-RTE"
    assert rows[0]["edge"] == {}


def test_get_workflow_recurrences_is_tenant_isolated_and_404s_for_missing_workflow(
    tmp_path, monkeypatch
):
    from api.store import put_run

    client = _client(tmp_path)
    monkeypatch.setenv("CONCORD_TENANT_KEYS", '{"tenant-a": "key-a", "tenant-b": "key-b"}')
    workflow_a = client.post(
        "/api/workflows",
        headers=_tenant("tenant-a", "key-a"),
        json={**_workflow_payload(), "name": "TenantAWorkflow"},
    ).json()["workflow_id"]
    workflow_b = client.post(
        "/api/workflows",
        headers=_tenant("tenant-b", "key-b"),
        json={**_workflow_payload(), "name": "TenantBWorkflow"},
    ).json()["workflow_id"]
    put_run(
        "RUN-TENANT-A",
        {
            "run": {"id": "RUN-TENANT-A", "workflow": "TenantAWorkflow"},
            "patches": [],
            "violations": [
                {
                    "contract_type": "evidence",
                    "severity": "HIGH",
                    "rule": "verified_sources_count must be > 0",
                    "failed_agent": "ReporterAgent",
                    "failed_step": 5,
                }
            ],
        },
        tenant_id="tenant-a",
        workflow_id=workflow_a,
        status="completed",
    )

    response_a = client.get(
        f"/api/workflows/{workflow_a}/recurrences",
        headers=_tenant("tenant-a", "key-a"),
    )
    response_b = client.get(
        f"/api/workflows/{workflow_b}/recurrences",
        headers=_tenant("tenant-b", "key-b"),
    )
    missing = client.get(
        f"/api/workflows/{workflow_a}/recurrences",
        headers=_tenant("tenant-b", "key-b"),
    )

    assert response_a.status_code == 200
    assert response_a.json()["recurrences"][0]["count"] == 1
    assert response_b.status_code == 200
    assert response_b.json()["recurrences"] == []
    assert missing.status_code == 404
