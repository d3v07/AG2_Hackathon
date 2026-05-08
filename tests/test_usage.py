"""Tenant usage and cost endpoint tests."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'usage.db'}")
    init_db()
    return TestClient(app)


def _key(tenant_id: str) -> str:
    from api.auth import create_api_key

    return create_api_key(tenant_id=tenant_id, name=f"{tenant_id} usage")["api_key"]


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def test_usage_endpoint_aggregates_current_tenant_only(tmp_path):
    client = _client(tmp_path)
    tenant_a = _key("tenant-a")
    tenant_b = _key("tenant-b")
    from api.store import put_run

    put_run(
        "RUN-A-1",
        {
            "run": {"id": "RUN-A-1", "workflow": "WF-A"},
            "patches": [],
            "violations": [],
            "cost": {
                "daytona_seconds": 1.25,
                "llm_tokens": 32,
                "llm_cost_usd": 0.00016,
                "daytona_cost_usd": 0.00025,
            },
        },
        tenant_id="tenant-a",
    )
    put_run(
        "RUN-A-2",
        {
            "run": {"id": "RUN-A-2", "workflow": "WF-A"},
            "patches": [],
            "violations": [],
            "cost": {
                "daytona_seconds": 2.5,
                "llm_tokens": 48,
                "llm_cost_usd": 0.00024,
                "daytona_cost_usd": 0.0005,
            },
        },
        tenant_id="tenant-a",
    )
    put_run(
        "RUN-B-1",
        {
            "run": {"id": "RUN-B-1", "workflow": "WF-B"},
            "patches": [],
            "violations": [],
            "cost": {
                "daytona_seconds": 9,
                "llm_tokens": 900,
                "llm_cost_usd": 0.09,
                "daytona_cost_usd": 0.09,
            },
        },
        tenant_id="tenant-b",
    )

    response = client.get("/api/tenant/usage", headers=_auth(tenant_a))
    other = client.get("/api/tenant/usage", headers=_auth(tenant_b))

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant-a",
        "period": "all",
        "run_count": 2,
        "daytona_seconds": 3.75,
        "llm_tokens": 80,
        "llm_cost_usd": 0.0004,
        "daytona_cost_usd": 0.00075,
        "total_cost_usd": 0.00115,
    }
    assert other.status_code == 200
    assert other.json()["run_count"] == 1
    assert other.json()["llm_tokens"] == 900


def test_usage_endpoint_requires_api_key(tmp_path):
    client = _client(tmp_path)
    from api.auth import create_api_key

    create_api_key(tenant_id="tenant-a", name="tenant-a usage")

    response = client.get("/api/tenant/usage")

    assert response.status_code == 401
    assert response.json()["detail"] == "missing API key"


def test_dashboard_cost_panel_is_wired_to_tenant_usage_endpoint():
    html = Path("public/index.html").read_text()

    assert "/api/tenant/usage" in html
    assert "function CostPanel" in html
    assert "LLM Tokens" in html
    assert "Daytona Cost" in html
