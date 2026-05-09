"""Release, CI, and onboarding artifact checks."""
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text()


def test_dockerfile_is_multistage_and_runs_fastapi():
    dockerfile = _read("Dockerfile")
    dockerignore = _read(".dockerignore")

    assert "FROM python:3.12-slim AS builder" in dockerfile
    assert "FROM python:3.12-slim AS runtime" in dockerfile
    assert "pip install --prefix=/install ." in dockerfile
    assert "USER concord" in dockerfile
    assert '${PORT:-8000}' in dockerfile
    assert "uvicorn api.index:app" in dockerfile
    assert ".env" in dockerignore
    assert ".env.*" in dockerignore


def test_compose_runs_api_and_falkordb_with_persistent_volume():
    compose = yaml.safe_load(_read("docker-compose.yml"))

    assert "api" in compose["services"]
    assert "falkordb" in compose["services"]
    api = compose["services"]["api"]
    falkor = compose["services"]["falkordb"]
    assert api["build"]["context"] == "."
    assert "8000:8000" in api["ports"]
    assert api["depends_on"]["falkordb"]["condition"] == "service_healthy"
    assert api["environment"]["FALKORDB_HOST"] == "falkordb"
    assert "CONCORD_ALLOW_DEV_AUTH" not in api["environment"]
    assert "concord-data:/app/data" in api["volumes"]
    assert "falkordb-data:/data" in falkor["volumes"]


def test_makefile_exposes_expected_release_targets():
    makefile = _read("Makefile")

    for target in ("dev:", "test:", "lint:", "fixture:", "smoke:", "clean:"):
        assert target in makefile
    assert "docker compose up --build api" in makefile
    assert "python3 -m ruff check ." in makefile
    assert "python3 run_all.py --fixture" in makefile


def test_ci_installs_dev_requirements_and_runs_lint_and_tests():
    """CI workflow shape — Sprint 20 #95 consolidated jobs into a 4-job
    matrix (backend-tests, frontend-vitest, frontend-e2e, frontend-a11y).
    Backend job carries the pytest + ruff steps."""
    raw = _read(".github/workflows/ci.yml")
    workflow = yaml.safe_load(raw)
    backend = workflow["jobs"]["backend-tests"]
    backend_run = "\n".join(
        step.get("run", "") for step in backend["steps"] if isinstance(step, dict)
    )

    # Trigger config: PRs from any branch (None == unset filter == all),
    # push on main/production
    assert "pull_request" in workflow["on"]
    assert "main" in workflow["on"]["push"]["branches"]
    assert "production" in workflow["on"]["push"]["branches"]
    # Concurrency cancels old runs
    assert workflow.get("concurrency", {}).get("cancel-in-progress") is True
    # Backend job runs ruff + pytest
    assert "python-version: '3.12'" in raw or 'python-version: "3.12"' in raw
    assert "ruff" in backend_run
    assert "pytest" in backend_run
    # Other expected jobs exist
    assert "frontend-vitest" in workflow["jobs"]
    assert "frontend-e2e" in workflow["jobs"]
    assert "frontend-a11y" in workflow["jobs"]


def test_dev_requirements_include_runtime_project_pytest_and_ruff():
    requirements = _read("requirements-dev.txt")

    assert "-e ." in requirements
    assert "pytest" in requirements
    assert "ruff" in requirements


def test_deployment_and_onboarding_docs_are_actionable():
    deployment = _read("docs/DEPLOYMENT.md")
    onboarding = _read("docs/ONBOARDING.md")

    for token in (
        "Render",
        "Railway",
        "CONCORD_DB_PATH",
        "DAYTONA_API_KEY",
        "Do not publish a tenant API key",
        "Branch protection",
        "Manual setting",
        "scripts/smoke_api.sh",
    ):
        assert token in deployment

    for token in (
        "POST /api/api-keys",
        "POST /api/workflows",
        "POST /api/runs",
        "GET /api/runs/",
        "GET /api/tenant/usage",
        "curl",
    ):
        assert token in onboarding

    assert "window.CONCORD_API_KEY" not in deployment
    assert "window.CONCORD_API_KEY" not in onboarding


def test_deploy_smoke_script_checks_health_endpoint():
    script = _read("scripts/smoke_api.sh")

    assert "set -euo pipefail" in script
    assert "/api/health" in script
    assert "status" in script
