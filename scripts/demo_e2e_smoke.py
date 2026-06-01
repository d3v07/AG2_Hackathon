"""Final Concord demo smoke.

Runs the smallest backend proof of the product loop:
API key -> workflow import -> run submission -> violations -> patches ->
validation state -> export-ready payload -> run-history revisit.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Iterator

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SAMPLE_TRACE = ROOT / "zone_b" / "fixtures" / "sample_trace.json"
CONTRACTS_YAML = ROOT / "zone_b" / "contracts" / "examples" / "literature_review.yaml"
VALIDATION_STATES = {
    "passed",
    "failed",
    "skipped",
    "unavailable",
    "credential_failure",
    "execution_error",
}


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Concord-API-Key": api_key,
        "Content-Type": "application/json",
    }


def _workflow_payload() -> dict[str, Any]:
    return {
        "name": "LiteratureReviewAssistant-DemoSmoke",
        "owner": "d3v07",
        "declared_topology": {
            "entry": "ResearcherAgent",
            "nodes": [
                {"id": "RES", "name": "ResearcherAgent", "kind": "agent"},
                {"id": "CRT", "name": "CriticAgent", "kind": "agent"},
                {"id": "VRF", "name": "VerifierAgent", "kind": "agent"},
                {"id": "RPT", "name": "ReporterAgent", "kind": "agent"},
                {"id": "ACT", "name": "ActionAgent", "kind": "agent"},
            ],
            "edges": [
                {"from": "ResearcherAgent", "to": "CriticAgent", "kind": "handoff"},
                {"from": "CriticAgent", "to": "VerifierAgent", "kind": "handoff"},
                {"from": "VerifierAgent", "to": "ReporterAgent", "kind": "handoff"},
                {"from": "ReporterAgent", "to": "ActionAgent", "kind": "handoff"},
            ],
        },
        "agents": [
            {"name": "ResearcherAgent"},
            {"name": "CriticAgent"},
            {"name": "VerifierAgent"},
            {"name": "ReporterAgent"},
            {"name": "ActionAgent"},
        ],
        "tools": [{"name": "tavily_search"}],
        "contracts_yaml": CONTRACTS_YAML.read_text(),
    }


@contextmanager
def _regression_runner(mode: str) -> Iterator[None]:
    previous = os.environ.get("CONCORD_REGRESSION_RUNNER")
    if mode == "local":
        os.environ["CONCORD_REGRESSION_RUNNER"] = "local"
    elif mode in {"product", "daytona"}:
        os.environ.pop("CONCORD_REGRESSION_RUNNER", None)
    else:
        raise ValueError("runner must be one of: product, daytona, local")
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("CONCORD_REGRESSION_RUNNER", None)
        else:
            os.environ["CONCORD_REGRESSION_RUNNER"] = previous


@contextmanager
def _maybe_quiet(verbose: bool) -> Iterator[None]:
    if verbose:
        yield
        return
    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


def _assert_response(response, expected: int, label: str) -> dict[str, Any]:
    if response.status_code != expected:
        raise AssertionError(
            f"{label} returned {response.status_code}; expected {expected}: {response.text}"
        )
    return response.json()


def _assert_export_ready(data: dict[str, Any]) -> None:
    required_top_level = {
        "run",
        "status",
        "stats",
        "topology",
        "contracts",
        "trace",
        "violations",
        "patches",
        "test",
        "cost",
        "report",
    }
    missing = sorted(required_top_level - set(data))
    if missing:
        raise AssertionError(f"run payload missing export field(s): {', '.join(missing)}")

    report = data["report"]
    test = data["test"]
    if report.get("validation_state") not in VALIDATION_STATES:
        raise AssertionError(f"unexpected report validation_state: {report.get('validation_state')}")
    if test.get("validation_state") not in VALIDATION_STATES:
        raise AssertionError(f"unexpected test validation_state: {test.get('validation_state')}")
    if not isinstance(report.get("validation_summary"), dict):
        raise AssertionError("report.validation_summary is missing")
    if not isinstance(test.get("assertions"), list):
        raise AssertionError("test.assertions is missing")


def run_demo_smoke(
    *,
    db_path: Path | None = None,
    runner: str = "product",
    verbose: bool = False,
) -> dict[str, Any]:
    from api.db import configure_database, init_db

    if db_path is None:
        tempdir = tempfile.TemporaryDirectory()
        db_path = Path(tempdir.name) / "concord-demo-smoke.db"
    else:
        tempdir = None

    try:
        configure_database(f"sqlite:///{db_path}")
        init_db()

        from api.index import app

        with _regression_runner(runner), TestClient(app) as client:
            health = _assert_response(client.get("/api/health"), 200, "health")
            if health.get("status") != "ok":
                raise AssertionError(f"health status was {health!r}")

            api_key = _assert_response(
                client.post(
                    "/api/api-keys",
                    json={"tenant_id": "local", "name": "Demo smoke"},
                ),
                201,
                "api key creation",
            )["api_key"]
            headers = _headers(api_key)

            workflow = _assert_response(
                client.post("/api/workflows", json=_workflow_payload(), headers=headers),
                200,
                "workflow import",
            )
            workflow_id = workflow["workflow_id"]
            if len(workflow.get("contracts", [])) != 5:
                raise AssertionError("workflow import did not normalize five contracts")

            raw_trace = json.loads(SAMPLE_TRACE.read_text())
            with _maybe_quiet(verbose):
                submitted = _assert_response(
                    client.post(
                        "/api/runs",
                        json={"workflow_id": workflow_id, "raw_trace": raw_trace},
                        headers=headers,
                    ),
                    202,
                    "run submission",
                )
            run_id = submitted["run_id"]

            status = _assert_response(
                client.get(f"/api/runs/{run_id}/status", headers=headers),
                200,
                "run status",
            )
            if status.get("status") != "completed":
                raise AssertionError(f"run did not complete: {status}")
            if status.get("status_history") != ["queued", "analyzing", "completed"]:
                raise AssertionError(f"unexpected status history: {status.get('status_history')}")

            data = _assert_response(
                client.get(f"/api/runs/{run_id}", headers=headers),
                200,
                "completed run fetch",
            )
            if data["stats"]["violations"] != 4:
                raise AssertionError(f"expected 4 violations, got {data['stats']['violations']}")
            if len(data["violations"]) != 4:
                raise AssertionError(f"expected 4 violation rows, got {len(data['violations'])}")
            if len(data["patches"]) != 4:
                raise AssertionError(f"expected 4 repair patches, got {len(data['patches'])}")
            if len(data["test"].get("assertions", [])) != 4:
                raise AssertionError(
                    f"expected 4 regression assertions, got {len(data['test'].get('assertions', []))}"
                )
            _assert_export_ready(data)

            history = _assert_response(client.get("/api/runs", headers=headers), 200, "run history")
            if run_id not in history.get("run_ids", []):
                raise AssertionError(f"run {run_id} was not present in run history")
            revisited = _assert_response(
                client.get(f"/api/runs/{run_id}", headers=headers),
                200,
                "history revisit",
            )
            if revisited["run"]["id"] != run_id:
                raise AssertionError("history revisit returned the wrong run")

            return {
                "run_id": run_id,
                "workflow_id": workflow_id,
                "violations": len(data["violations"]),
                "patches": len(data["patches"]),
                "assertions": len(data["test"].get("assertions", [])),
                "validation_state": data["test"].get("validation_state"),
                "sandbox_id": data["test"].get("sandbox_id"),
                "history_count": len(history.get("run_ids", [])),
            }
    finally:
        if tempdir is not None:
            tempdir.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the final Concord demo smoke.")
    parser.add_argument(
        "--runner",
        choices=["product", "daytona", "local"],
        default=os.environ.get("CONCORD_DEMO_REGRESSION_RUNNER", "product"),
        help="Regression execution path. product/daytona uses the default sandbox path; local is deterministic.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ["CONCORD_DEMO_DB"]) if os.environ.get("CONCORD_DEMO_DB") else None,
        help="Optional SQLite database path.",
    )
    parser.add_argument("--verbose", action="store_true", help="Show agent transcript output.")
    args = parser.parse_args()

    summary = run_demo_smoke(db_path=args.db, runner=args.runner, verbose=args.verbose)
    print("PASS demo_e2e_smoke")
    print(
        " ".join(
            [
                f"run_id={summary['run_id']}",
                f"workflow_id={summary['workflow_id']}",
                f"violations={summary['violations']}",
                f"patches={summary['patches']}",
                f"assertions={summary['assertions']}",
                f"validation_state={summary['validation_state']}",
                f"sandbox_id={summary['sandbox_id']}",
                f"history_count={summary['history_count']}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
