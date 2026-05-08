from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk"))


class _TestClientTransport:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def __call__(self, method: str, path: str, *, headers: dict, json_body: dict | None, timeout: float):
        return self.client.request(method, path, headers=headers, json=json_body)


class _RecordingClient:
    def __init__(self) -> None:
        self.raw_trace: dict | None = None

    def register_workflow(self, definition: dict) -> dict:
        return {"workflow_id": "WF-REC"}

    def submit_run(self, workflow_id: str, raw_trace: dict) -> dict[str, str]:
        self.raw_trace = raw_trace
        return {"run_id": "RUN-REC", "status": "queued"}


def _api_client(tmp_path) -> TestClient:
    from api.db import configure_database, init_db
    from api.index import app

    configure_database(f"sqlite:///{tmp_path / 'sdk.db'}")
    init_db()
    return TestClient(app)


def _workflow_definition() -> dict:
    return {
        "name": "SDKWorkflow",
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
    }


def test_sdk_declares_zone_a_swarm_runtime_extra():
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "sdk/pyproject.toml").read_text())
    dependencies = pyproject["project"]["dependencies"]

    assert any(dependency.startswith("ag2[openai]") for dependency in dependencies)


def test_sdk_imports_without_repo_root_on_pythonpath(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "sdk")

    result = subprocess.run(
        [sys.executable, "-c", "import concord_sdk; print(concord_sdk.ConcordClient.__name__)"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ConcordClient"


def test_concord_client_submits_raw_trace_to_existing_api(tmp_path, clean_trace_raw):
    from concord_sdk import ConcordClient

    api = _api_client(tmp_path)
    client = ConcordClient(
        api_url="http://testserver",
        transport=_TestClientTransport(api),
    )

    workflow = client.register_workflow(_workflow_definition())
    submitted = client.submit_run(workflow["workflow_id"], clean_trace_raw)
    fetched = client.get_run(submitted["run_id"])

    assert submitted["status"] == "queued"
    assert fetched["status"] == "completed"
    assert fetched["run"]["id"] == submitted["run_id"]


def test_concord_client_rejects_non_local_tenant_without_key(tmp_path):
    from concord_sdk import ConcordAPIError, ConcordClient

    api = _api_client(tmp_path)
    client = ConcordClient(
        api_url="http://testserver",
        tenant_id="tenant-a",
        transport=_TestClientTransport(api),
    )

    try:
        client.register_workflow(_workflow_definition())
    except ConcordAPIError as exc:
        assert exc.status_code == 401
        assert "tenant credentials" in exc.body
    else:
        raise AssertionError("non-local tenant request succeeded without a key")


def test_instrument_wires_agents_and_submits_trace(tmp_path, clean_trace_raw, monkeypatch):
    from concord_sdk import ConcordClient, instrument
    import concord_sdk.instrumentation as sdk_instrumentation
    from zone_a.swarm import build_swarm

    calls: list[str] = []

    def fake_instrument_agent(agent, *, tracer_provider):
        calls.append(agent.name)
        return agent

    monkeypatch.setattr(sdk_instrumentation, "instrument_agent", fake_instrument_agent)
    api = _api_client(tmp_path)
    client = ConcordClient(
        api_url="http://testserver",
        transport=_TestClientTransport(api),
    )
    agents, _ = build_swarm(llm_config={"config_list": [{"model": "test", "api_key": "x"}]})

    session = instrument(
        agents,
        api_url="http://testserver",
        api_key="",
        client=client,
        workflow_definition=_workflow_definition(),
        run_trace=clean_trace_raw,
    )

    assert calls == [agent.name for agent in agents]
    assert session.workflow_id.startswith("WF-")
    assert session.last_run_id
    assert client.get_status(session.last_run_id)["status"] == "completed"


def test_instrumentation_complete_submits_subsequent_trace(tmp_path, clean_trace_raw):
    from concord_sdk import ConcordClient, instrument

    api = _api_client(tmp_path)
    client = ConcordClient(
        api_url="http://testserver",
        transport=_TestClientTransport(api),
    )
    workflow = client.register_workflow(_workflow_definition())
    session = instrument(
        [],
        api_url="http://testserver",
        api_key="",
        client=client,
        workflow_id=workflow["workflow_id"],
    )

    submitted = session.complete(clean_trace_raw)

    assert submitted["run_id"] == session.last_run_id
    assert client.get_run(session.last_run_id)["status"] == "completed"


def test_instrumentation_complete_prefers_captured_native_spans():
    from concord_sdk import instrument

    client = _RecordingClient()
    session = instrument(
        [],
        api_url="http://testserver",
        api_key="",
        client=client,
        workflow_id="WF-REC",
    )
    tracer = session.tracer_provider.get_tracer("concord.test")
    with tracer.start_as_current_span(
        "invoke_agent VerifierAgent",
        attributes={
            "ag2.span.type": "agent",
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "VerifierAgent",
            "gen_ai.output.messages": '[{"role":"assistant","parts":[{"type":"text","content":"Verified."}]}]',
        },
    ):
        pass

    session.complete(
        {
            "run_id": "run_native",
            "workflow_name": "Workflow",
            "events": [],
            "final_output": {"summary": "done"},
        }
    )

    assert client.raw_trace is not None
    assert client.raw_trace["run_id"] == "run_native"
    assert client.raw_trace["final_output"] == {"summary": "done"}
    assert client.raw_trace["events"][0]["agent"] == "VerifierAgent"
    assert client.raw_trace["events"][0]["content"] == "Verified."


def test_instrumentation_complete_does_not_resubmit_previous_spans():
    from concord_sdk import instrument

    client = _RecordingClient()
    session = instrument(
        [],
        api_url="http://testserver",
        api_key="",
        client=client,
        workflow_id="WF-REC",
    )
    tracer = session.tracer_provider.get_tracer("concord.test")
    with tracer.start_as_current_span(
        "invoke_agent ResearcherAgent",
        attributes={
            "ag2.span.type": "agent",
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "ResearcherAgent",
            "gen_ai.output.messages": '[{"role":"assistant","parts":[{"type":"text","content":"First."}]}]',
        },
    ):
        pass
    session.complete({"run_id": "run_first", "workflow_name": "Workflow", "events": []})

    with tracer.start_as_current_span(
        "invoke_agent VerifierAgent",
        attributes={
            "ag2.span.type": "agent",
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "VerifierAgent",
            "gen_ai.output.messages": '[{"role":"assistant","parts":[{"type":"text","content":"Second."}]}]',
        },
    ):
        pass
    session.complete({"run_id": "run_second", "workflow_name": "Workflow", "events": []})

    assert client.raw_trace is not None
    assert client.raw_trace["run_id"] == "run_second"
    assert [event["agent"] for event in client.raw_trace["events"]] == ["VerifierAgent"]
    assert client.raw_trace["events"][0]["content"] == "Second."
