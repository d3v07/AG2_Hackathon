"""Background run processing for submitted traces."""
from __future__ import annotations

import asyncio
from typing import Any

from api.adapter import report_to_concord_data
from api.store import get_run_inputs, set_run_status
from zone_b.agents.attribution import run_attribution
from zone_b.agents.contract_checker import run_contract_checker
from zone_b.agents.regression_test import run_regression_test
from zone_b.agents.repair import run_repair
from zone_b.agents.reporter import run_reporter
from zone_b.agents.trace_collector import run_trace_collector


def process_run(run_id: str, tenant_id: str = "local") -> None:
    try:
        asyncio.run(_process_run(run_id, tenant_id))
    except Exception as exc:
        set_run_status(run_id, "failed", tenant_id=tenant_id, error=str(exc))


async def _process_run(run_id: str, tenant_id: str) -> None:
    inputs = get_run_inputs(run_id, tenant_id)
    if inputs is None:
        raise ValueError(f"run {run_id} not found")

    set_run_status(run_id, "analyzing", tenant_id=tenant_id)
    raw_trace = inputs.get("raw_trace")
    if raw_trace is None:
        raise ValueError("task_spec execution requires Zone A runtime credentials")
    if not isinstance(raw_trace.get("events"), list):
        raise ValueError("raw_trace.events must be a list")

    collected = await run_trace_collector(raw_trace)
    checked = run_contract_checker(collected["run_trace"], collected["context_snapshot"])
    violations = checked["violations"]

    if violations:
        attributed = await run_attribution(
            violations, collected["run_trace"], collected["context_snapshot"]
        )
        repaired = await run_repair(
            violations, attributed["failed_agent"], attributed["failed_step"]
        )
        tested = await run_regression_test(
            repaired["repair_patch"], violations, collected["run_trace"]
        )
        reported = await run_reporter(
            collected["run_trace"],
            violations,
            attributed,
            repaired,
            tested,
            collected["context_snapshot"],
            approval_status="pending",
        )
        report = reported["report"]
    else:
        report = _clean_report(raw_trace)

    violation_dicts = report.get("violations", [])
    data = report_to_concord_data(report, raw_trace, violation_dicts)
    data["run"]["id"] = run_id
    data["status"] = "completed"
    set_run_status(run_id, "completed", tenant_id=tenant_id, report=data)


def _clean_report(raw_trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": raw_trace.get("run_id", ""),
        "workflow_name": raw_trace.get("workflow_name", ""),
        "violation_count": 0,
        "severity_summary": {"high": 0, "medium": 0, "low": 0},
        "failed_agent": "",
        "failed_step": -1,
        "likely_root_cause": "",
        "repair_patch": "",
        "affected_primitive": "",
        "patch_code": "",
        "regression_test_status": "passed",
        "repair_confidence": 0.0,
        "approval_status": "approved",
        "violations": [],
        "patches": [],
        "regression_tests": [],
        "regression_summary": {"pass": 0, "fail": 0, "error": 0},
        "narrative": "No contract violations were detected for this run.",
    }
