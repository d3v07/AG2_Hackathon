"""Golden snapshot regression test for raw_trace POST /api/runs.

Locks the existing raw_trace path's CONCORD_DATA shape so any unintended
change anywhere in the api/Zone B/adapter pipeline is caught immediately.

Sprints 13-20 modify various pieces of this pipeline; this test must remain
green throughout. The only field normalized is `run.id` (UUID-generated);
every other field is asserted bit-identical against the committed golden.

Regenerate the golden when the shape *intentionally* changes:
    UPDATE_GOLDEN=1 pytest tests/test_runs_raw_trace_regression.py
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


GOLDEN_PATH = Path(__file__).parent / "golden" / "raw_trace_concord_data.json"
RUN_ID_PLACEHOLDER = "RUN-FIXED-FOR-GOLDEN"
TIMESTAMP_PLACEHOLDER = "2026-01-01T00:00:00Z"


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
            "name": "GoldenSnapshotWorkflow",
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


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    """Strip dynamic fields so the rest of CONCORD_DATA can be compared bit-identical."""
    normalized = deepcopy(data)
    if isinstance(normalized.get("run"), dict):
        normalized["run"]["id"] = RUN_ID_PLACEHOLDER
    report = normalized.get("report")
    if isinstance(report, dict):
        approval = report.get("approval")
        if isinstance(approval, dict) and "requested_at" in approval:
            approval["requested_at"] = TIMESTAMP_PLACEHOLDER
    return normalized


def test_raw_trace_concord_data_matches_golden(tmp_path, clean_trace_raw):
    """Submit a known clean raw_trace and assert CONCORD_DATA matches the committed golden."""
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

    actual = _normalize(fetched.json())

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"Golden regenerated at {GOLDEN_PATH}")

    assert GOLDEN_PATH.exists(), (
        f"Golden file missing: {GOLDEN_PATH}. "
        f"Generate with: UPDATE_GOLDEN=1 pytest {__file__}"
    )

    expected = json.loads(GOLDEN_PATH.read_text())
    assert actual == expected, (
        "CONCORD_DATA shape changed. If the change is intentional, regenerate the "
        f"golden with: UPDATE_GOLDEN=1 pytest {__file__}"
    )
