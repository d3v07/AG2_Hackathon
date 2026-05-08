"""Run event stream API tests."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'run-events.db'}")
    init_db()
    return TestClient(app)


def _workflow_id(client: TestClient, name: str = "EventWorkflow", headers: dict | None = None) -> str:
    response = client.post(
        "/api/workflows",
        headers=headers or {},
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


def _tenant(tenant_id: str, key: str) -> dict[str, str]:
    return {"X-Tenant-ID": tenant_id, "X-Concord-API-Key": key}


def _read_event_stream(client: TestClient, path: str, headers: dict | None = None) -> list[dict]:
    with client.stream("GET", path, headers=headers or {}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode()

    events: list[dict] = []
    for block in body.strip().split("\n\n"):
        data_lines = [line.removeprefix("data: ") for line in block.splitlines() if line.startswith("data: ")]
        if data_lines:
            events.append(json.loads("\n".join(data_lines)))
    return events


def test_run_events_replay_completed_status_history(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    run_id = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    ).json()["run_id"]

    events = _read_event_stream(client, f"/api/runs/{run_id}/events")

    assert [event["status"] for event in events] == ["queued", "analyzing", "completed"]
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert events[-1]["terminal"] is True
    assert events[-1]["status_history"] == ["queued", "analyzing", "completed"]


def test_run_events_replay_skips_events_at_or_before_last_event_id(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    run_id = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    ).json()["run_id"]

    events = _read_event_stream(
        client,
        f"/api/runs/{run_id}/events",
        headers={"Last-Event-ID": "2"},
    )

    assert [event["status"] for event in events] == ["completed"]
    assert [event["sequence"] for event in events] == [3]


def test_run_events_rejects_invalid_last_event_id(tmp_path, clean_trace_raw):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    run_id = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    ).json()["run_id"]

    response = client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "abc"})

    assert response.status_code == 400


def test_run_events_replay_failed_terminal_status_with_error(tmp_path):
    client = _client(tmp_path)
    workflow_id = _workflow_id(client)
    run_id = client.post(
        "/api/runs",
        json={"workflow_id": workflow_id, "raw_trace": {"events": "not-a-list"}},
    ).json()["run_id"]

    events = _read_event_stream(client, f"/api/runs/{run_id}/events")

    assert [event["status"] for event in events] == ["queued", "analyzing", "failed"]
    assert events[-1]["terminal"] is True
    assert "raw_trace.events" in events[-1]["error"]


def test_run_events_endpoint_404_for_unknown_run(tmp_path):
    client = _client(tmp_path)

    response = client.get("/api/runs/RUN-MISSING/events")

    assert response.status_code == 404


def test_run_events_are_tenant_isolated(tmp_path, clean_trace_raw, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv("CONCORD_TENANT_KEYS", '{"tenant-a":"key-a","tenant-b":"key-b"}')
    headers_a = _tenant("tenant-a", "key-a")
    headers_b = _tenant("tenant-b", "key-b")
    workflow_id = _workflow_id(client, "TenantEventWorkflow", headers=headers_a)
    run_id = client.post(
        "/api/runs",
        headers=headers_a,
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    ).json()["run_id"]

    events = _read_event_stream(client, f"/api/runs/{run_id}/events", headers=headers_a)
    response_b = client.get(f"/api/runs/{run_id}/events", headers=headers_b)
    response_local = client.get(f"/api/runs/{run_id}/events")

    assert events[-1]["status"] == "completed"
    assert response_b.status_code == 404
    assert response_local.status_code == 404


def test_run_events_accepts_stream_token_without_custom_headers(tmp_path, clean_trace_raw, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv("CONCORD_TENANT_KEYS", '{"tenant-a":"key-a"}')
    headers = _tenant("tenant-a", "key-a")
    workflow_id = _workflow_id(client, "TokenEventWorkflow", headers=headers)
    run_id = client.post(
        "/api/runs",
        headers=headers,
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    ).json()["run_id"]

    token_response = client.post(f"/api/runs/{run_id}/events/token", headers=headers)
    token = token_response.json()["stream_token"]
    events = _read_event_stream(client, f"/api/runs/{run_id}/events?stream_token={token}")

    assert token_response.status_code == 200
    assert token_response.json()["expires_in"] > 0
    assert [event["status"] for event in events] == ["queued", "analyzing", "completed"]


def test_run_events_rejects_invalid_stream_token(tmp_path, clean_trace_raw, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setenv("CONCORD_TENANT_KEYS", '{"tenant-a":"key-a"}')
    headers = _tenant("tenant-a", "key-a")
    workflow_id = _workflow_id(client, "BadTokenWorkflow", headers=headers)
    run_id = client.post(
        "/api/runs",
        headers=headers,
        json={"workflow_id": workflow_id, "raw_trace": clean_trace_raw},
    ).json()["run_id"]

    response = client.get(f"/api/runs/{run_id}/events?stream_token=not-valid")

    assert response.status_code == 401


def test_event_bus_subscribers_are_scoped_by_tenant_and_run():
    from api.events import RunEventBus

    bus = RunEventBus()
    tenant_a = bus.subscribe("tenant-a", "RUN-1")
    tenant_b = bus.subscribe("tenant-b", "RUN-1")
    run_two = bus.subscribe("tenant-a", "RUN-2")

    bus.publish("tenant-a", "RUN-1", {"status": "analyzing"})

    assert tenant_a.get_nowait()["status"] == "analyzing"
    assert tenant_b.get_nowait() is None
    assert run_two.get_nowait() is None

    tenant_a.close()
    tenant_b.close()
    run_two.close()
    assert bus.subscriber_count("tenant-a", "RUN-1") == 0


def test_event_stream_tokens_expire_and_bind_to_run():
    from api.events import RunEventTokenStore

    store = RunEventTokenStore()
    valid = store.create("tenant-a", "RUN-1", ttl_seconds=300)
    expired = store.create("tenant-a", "RUN-1", ttl_seconds=0)

    assert store.validate(valid, "RUN-1") == "tenant-a"
    assert store.validate(valid, "RUN-2") is None
    assert store.validate(expired, "RUN-1") is None
