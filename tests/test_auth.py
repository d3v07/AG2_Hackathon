"""API key authentication tests."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'auth.db'}")
    init_db()
    return TestClient(app)


def _remote_client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'remote-auth.db'}")
    init_db()
    return TestClient(app, client=("203.0.113.10", 50000))


def test_health_endpoint_remains_public(tmp_path):
    client = _client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_key_status_endpoint_is_public(tmp_path):
    client = _client(tmp_path)

    assert client.get("/api/api-keys/status").json() == {
        "requires_api_key": False,
        "can_create_first_key": True,
        "authenticated": False,
        "tenant_id": "",
    }
    created = client.post(
        "/api/api-keys",
        json={"tenant_id": "local", "name": "local primary"},
    )
    assert created.status_code == 201

    response = client.get("/api/api-keys/status")

    assert response.status_code == 200
    assert response.json() == {
        "requires_api_key": True,
        "can_create_first_key": False,
        "authenticated": False,
        "tenant_id": "",
    }


def test_api_key_status_reports_bootstrap_and_session_state(tmp_path):
    remote = _remote_client(tmp_path)

    response = remote.get("/api/api-keys/status")

    assert response.status_code == 200
    assert response.json() == {
        "requires_api_key": False,
        "can_create_first_key": False,
        "authenticated": False,
        "tenant_id": "",
    }

    client = _client(tmp_path)
    created = client.post(
        "/api/api-keys",
        json={"tenant_id": "tenant-a", "name": "tenant-a primary"},
    ).json()

    valid = client.get("/api/api-keys/status", headers={"Authorization": f"Bearer {created['api_key']}"})
    invalid = client.get("/api/api-keys/status", headers={"Authorization": "Bearer concord_invalid"})

    assert valid.status_code == 200
    assert valid.json()["authenticated"] is True
    assert valid.json()["tenant_id"] == "tenant-a"
    assert invalid.status_code == 200
    assert invalid.json()["authenticated"] is False


def test_protected_api_routes_require_api_key(tmp_path):
    client = _client(tmp_path)
    from api.auth import create_api_key

    create_api_key(tenant_id="tenant-a", name="tenant-a primary")

    response = client.get("/api/workflows")

    assert response.status_code == 401
    assert response.json()["detail"] == "missing API key"


def test_post_api_keys_bootstraps_first_key_and_bearer_sets_tenant(tmp_path):
    client = _client(tmp_path)

    created = client.post(
        "/api/api-keys",
        json={"tenant_id": "tenant-a", "name": "tenant-a primary"},
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["tenant_id"] == "tenant-a"
    assert payload["api_key"].startswith("concord_")

    response = client.post(
        "/api/workflows",
        headers={"Authorization": f"Bearer {payload['api_key']}"},
        json={
            "name": "TenantAWorkflow",
            "owner": "d3v07",
            "declared_topology": {"entry": "ResearcherAgent", "edges": []},
            "agents": [{"name": "ResearcherAgent"}],
            "tools": [],
            "contracts": [{"id": "C-EVD", "type": "evidence", "rule": "verified_sources_count > 0"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-a"


def test_first_api_key_bootstrap_is_limited_to_local_dev_requests(tmp_path):
    client = _remote_client(tmp_path)

    response = client.post(
        "/api/api-keys",
        json={"tenant_id": "tenant-a", "name": "tenant-a primary"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "missing API key"


def test_authenticated_key_creation_defaults_to_current_tenant(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/api/api-keys",
        json={"tenant_id": "tenant-a", "name": "tenant-a primary"},
    ).json()

    rotated = client.post(
        "/api/api-keys",
        headers={"Authorization": f"Bearer {created['api_key']}"},
        json={"name": "tenant-a rotation"},
    )

    assert rotated.status_code == 201
    assert rotated.json()["tenant_id"] == "tenant-a"


def test_invalid_api_key_returns_401(tmp_path):
    client = _client(tmp_path)

    response = client.get(
        "/api/workflows",
        headers={"Authorization": "Bearer concord_invalid"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid API key"
