"""Completed-run product coherence checks."""
from __future__ import annotations

from pathlib import Path


def _app_source() -> str:
    return Path("public/app.jsx").read_text()


def _fixture_source() -> str:
    return Path("public/data.js").read_text()


def test_public_app_no_longer_uses_visible_lite_branding():
    app = _app_source()
    html = Path("public/index.html").read_text()
    api = Path("api/index.py").read_text()

    assert "CONCORD · LITE" not in app
    assert "concord-lite" not in app
    assert "Concord Lite · Mission Control" not in html
    assert "<title>Concord · Mission Control</title>" in html
    assert 'title="Concord API"' in api
    assert "Concord Lite API" not in api


def test_violation_rows_show_contract_to_repair_path():
    source = _app_source()
    fixture = _fixture_source()

    assert "regressionForViolation" in source
    assert "testAssertionStats" in source
    assert "assertionRepairLink" in source
    assert "repair-path" in source
    assert "Evidence" in source
    assert "AG2 primitive" in source
    assert "Regression" in source
    assert "VIEW PATCH" in source
    assert "violation_id" in fixture
    assert "patch_id" in fixture


def test_completed_run_claims_are_data_driven():
    source = _app_source()

    assert "1 tool event" not in source
    assert "4 violations</div>" not in source
    assert "4 AG2 primitives inserted" not in source
    assert "4 / 4 passed" not in source
    assert "t.assertions.length} passed" not in source
    assert "started 14:22:08 UTC" not in source
    assert "3 HIGH" not in source
    assert "4 PATCHES" not in source
    assert "7 sources" not in source
    assert "0 sources" not in source
    assert "formatRunStarted" in source
    assert "severitySummary" in source
    assert "latestTraceContextValue" in source
