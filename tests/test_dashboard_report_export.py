"""Static checks for completed-run report export wiring."""
from __future__ import annotations

from pathlib import Path


def _app_source() -> str:
    return Path("public/app.jsx").read_text()


def test_report_export_button_is_wired_to_download_and_clipboard():
    source = _app_source()

    assert "function buildReportExportPayload(data)" in source
    assert "async function exportReportJson(data)" in source
    assert "downloadReportJson(filename, jsonText)" in source
    assert "writeClipboardText(jsonText)" in source
    assert "onClick={handleExport}" in source
    assert "EXPORTED + COPIED" in source


def test_report_export_payload_contains_complete_contract_to_repair_fields():
    source = _app_source()

    for field in [
        "verdicts:",
        "violation_count:",
        "severity_summary:",
        "evidence:",
        "violations:",
        "patches:",
        "regression:",
        "regression_tests:",
        "regression_summary:",
        "sandbox_id:",
        "cost,",
        "report,",
    ]:
        assert field in source


def test_report_export_filename_uses_run_id():
    source = _app_source()

    assert "function reportExportFilename(data)" in source
    assert "data?.run?.id" in source
    assert "concord-report-${safeRunId}.json" in source
