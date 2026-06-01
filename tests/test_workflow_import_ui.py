"""Static checks for in-product workflow import."""
from __future__ import annotations

from pathlib import Path


def _app_source() -> str:
    return Path("public/app.jsx").read_text()


def test_landing_exposes_workflow_import_panel():
    source = _app_source()

    assert "Import workflow contract" in source
    assert "workflow-import-spec" in source
    assert "workflow-import-name" in source
    assert "Paste JSON workflow spec or YAML contract DSL" in source


def test_workflow_import_posts_to_existing_workflow_api_and_refreshes_picker():
    source = _app_source()

    assert 'fetch("/api/workflows"' in source
    assert 'fetch("/api/public/workflows"' in source
    assert "importWorkflowPayload" in source
    assert "postWorkflowImportPayload" in source
    assert "setWorkflows((current)" in source
    assert "setWorkflowId(created.workflow_id" in source


def test_workflow_import_surfaces_server_validation_errors_inline():
    source = _app_source()

    assert "importError" in source
    assert "Validation error:" in source
    assert "must be an array." in source
    assert "aria-live=\"polite\"" in source
