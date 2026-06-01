"""Background run processing for submitted traces."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from api.adapter import report_to_concord_data
from api.store import get_run_inputs, set_run_status
from zone_a.swarm import run_swarm
from zone_b.agents.attribution import run_attribution
from zone_b.agents.contract_checker import run_contract_checker
from zone_b.agents.reporter import run_reporter
from zone_b.agents.trace_collector import run_trace_collector
from zone_b.orchestrator import run_repair_test_iterations


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
    task_spec = inputs.get("task_spec")

    if raw_trace is None and task_spec is not None:
        raw_trace = await _execute_zone_a_from_task_spec(task_spec, run_id)

    if raw_trace is None:
        raise ValueError("run has neither raw_trace nor task_spec")
    if not isinstance(raw_trace.get("events"), list):
        raise ValueError("raw_trace.events must be a list")

    collected = await run_trace_collector(raw_trace)
    checked = run_contract_checker(
        collected["run_trace"],
        collected["context_snapshot"],
        spans=collected.get("spans"),
    )
    violations = checked["violations"]

    if violations:
        attributed = await run_attribution(
            violations, collected["run_trace"], collected["context_snapshot"]
        )
        iteration = await run_repair_test_iterations(
            violations,
            collected["run_trace"],
            attributed["failed_agent"],
            attributed["failed_step"],
        )
        repaired = iteration["repair"]
        tested = iteration["regression"]
        reported = await run_reporter(
            collected["run_trace"],
            violations,
            attributed,
            repaired,
            tested,
            collected["context_snapshot"],
            approval_status="pending",
            iteration_count=iteration["iteration_count"],
        )
        report = reported["report"]
    else:
        report = _clean_report(raw_trace)

    violation_dicts = report.get("violations", [])
    data = report_to_concord_data(report, raw_trace, violation_dicts)
    data["run"]["id"] = run_id
    data["status"] = "completed"
    set_run_status(run_id, "completed", tenant_id=tenant_id, report=data)


async def _execute_zone_a_from_task_spec(
    task_spec: dict[str, Any], run_id: str
) -> dict[str, Any]:
    """Run the Zone A swarm from a task_spec and return the resulting raw_trace dict.

    Live mode is the product default. Stub mode remains available for
    deterministic internal tests. The swarm writes the trace JSON to a temp
    file; we read it back, parse it, and hand it off to the existing Zone B
    pipeline.
    """
    task = task_spec.get("task")
    research_question = task_spec.get("research_question")
    mode = task_spec.get("mode", "live")

    if not task or not research_question:
        raise ValueError("task_spec requires non-empty task and research_question")

    with tempfile.TemporaryDirectory() as tmpdir:
        trace_path = Path(tmpdir) / f"{run_id}.json"
        await run_swarm(
            task=task,
            research_question=research_question,
            run_id=run_id,
            fixture_path=None,
            output_path=trace_path,
            mode=mode,
        )
        return json.loads(trace_path.read_text())


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
        "regression_test_status": "skipped",
        "validation_state": "skipped",
        "repair_confidence": 0.0,
        "approval_status": "approved",
        "violations": [],
        "patches": [],
        "regression_tests": [],
        "regression_summary": {"pass": 0, "fail": 0, "error": 0},
        "validation_summary": {
            "passed": 0,
            "failed": 0,
            "skipped": 1,
            "unavailable": 0,
            "credential_failure": 0,
            "execution_error": 0,
        },
        "iteration_count": 0,
        "sandbox_id": "",
        "regression_duration_ms": 0,
        "regression_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "regression_cost": {
            "daytona_seconds": 0,
            "llm_tokens": 0,
            "llm_cost_usd": 0,
            "daytona_cost_usd": 0,
        },
        "narrative": "No contract violations were detected for this run.",
    }
