"""Sprint 15 #72 — backward-compat test for legacy raw_trace runs without spans[].

This test PASSES today (before the spans block lands in #74) using a
forward-compatible `data.get("spans", [])` lookup. It locks the contract
that the new spans block must be ADDITIVE — the legacy 12-key CONCORD_DATA
shape (run, stats, agents, topology, routes, contracts, trace, violations,
patches, test, cost, report) must remain intact when spans is absent or
empty.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


REQUIRED_TOP_LEVEL_KEYS = {
    "run",
    "stats",
    "agents",
    "topology",
    "routes",
    "contracts",
    "trace",
    "violations",
    "patches",
    "test",
    "cost",
    "report",
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
            "name": "SpansEmptyCompatWorkflow",
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


def test_legacy_raw_trace_has_no_spans_or_empty_spans(tmp_path, clean_trace_raw):
    """Legacy raw_trace path must not break when spans block is absent."""
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    submitted = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    )
    assert submitted.status_code == 202

    run_id = submitted.json()["run_id"]
    fetched = client.get(f"/api/runs/{run_id}")
    assert fetched.status_code == 200
    data = fetched.json()

    assert data.get("spans", []) == [], (
        "Legacy raw_trace path must yield empty spans (or omit the key entirely). "
        f"Got: {data.get('spans')!r}"
    )


def test_legacy_concord_data_shape_intact(tmp_path, clean_trace_raw):
    """Every existing top-level key must still be present (additive-only contract)."""
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)

    submitted = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    )
    run_id = submitted.json()["run_id"]
    data = client.get(f"/api/runs/{run_id}").json()

    missing = REQUIRED_TOP_LEVEL_KEYS - set(data.keys())
    assert not missing, f"Missing required top-level keys: {missing}"

    assert isinstance(data["trace"], list) and data["trace"], "trace[] must be non-empty"
