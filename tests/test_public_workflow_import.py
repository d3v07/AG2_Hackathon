"""Public same-origin workflow import relay tests."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'public-workflows.db'}")
    init_db()
    return TestClient(app)


def _workflow_payload() -> dict:
    return {
        "name": "ImportedWorkflow",
        "owner": "d3v07",
        "declared_topology": {},
        "agents": [],
        "tools": [],
        "contracts": [],
        "contracts_yaml": """
contracts:
  evidence:
    id: C-EVD
    rule: verified_sources_count must be > 0 before ReporterAgent runs
""",
    }


def test_public_workflow_import_is_disabled_by_default(tmp_path):
    client = _client(tmp_path)

    response = client.post("/api/public/workflows", json=_workflow_payload())

    assert response.status_code == 403
    assert response.json()["detail"] == "public workflow import is disabled"


def test_public_workflow_import_uses_existing_validation_and_tenant(tmp_path, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv("CONCORD_PUBLIC_WORKFLOWS_ENABLED", "1")
    monkeypatch.setenv("CONCORD_PUBLIC_TENANT_ID", "public-tenant")

    response = client.post("/api/public/workflows", json=_workflow_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "public-tenant"
    assert body["name"] == "ImportedWorkflow"
    assert body["contracts"][0]["id"] == "C-EVD"


def test_public_workflow_import_returns_contract_validation_errors(tmp_path, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv("CONCORD_PUBLIC_WORKFLOWS_ENABLED", "1")
    payload = _workflow_payload()
    payload["contracts_yaml"] = """
contracts:
  - id: C-BAD
    type: evidence
"""

    response = client.post("/api/public/workflows", json=payload)

    assert response.status_code == 400
    assert "contracts[0]" in response.json()["detail"]
    assert "rule" in response.json()["detail"]
