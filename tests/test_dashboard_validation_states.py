"""Static coverage for dashboard validation state rendering."""
from __future__ import annotations

from pathlib import Path


def _app_source() -> str:
    return Path("public/app.jsx").read_text()


def _served_fixture_source() -> str:
    return Path("public/index.html").read_text()


def test_dashboard_defines_all_validation_state_labels():
    source = _app_source()

    assert "validationLabel" in source
    assert "validationPillKind" in source
    for label in [
        "PASSED",
        "FAILED",
        "SKIPPED",
        "UNAVAILABLE",
        "CREDENTIAL FAILURE",
        "EXECUTION ERROR",
    ]:
        assert label in source


def test_export_payload_includes_validation_state():
    source = _app_source()

    assert "validation_state:" in source
    assert "report.validation_state" in source
    assert "test.validation_state" in source


def test_served_fixture_data_includes_validation_state():
    source = _served_fixture_source()

    assert 'validation_state: "passed"' in source
    assert "validation_summary: { passed: 4" in source
    assert 'validation_state: "passed", violation_id: "V-001"' in source
