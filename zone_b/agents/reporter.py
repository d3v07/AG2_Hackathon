"""Reporter — assembles the final Contract Violation Report.

Per issue #2: most fields are direct dict assembly from upstream outputs;
the LLM is only used to generate the human-readable narrative summary.
"""
import asyncio
import json
from autogen import ConversableAgent
from shared.models import RunTrace, ContextSnapshot, Violation
from zone_b.config import get_llm_config
from zone_b.utils import make_proxy as _make_proxy


def _violations_to_dicts(violations: list[Violation]) -> list[dict]:
    return [
        {
            "contract_type": v.contract_type,
            "severity": v.severity,
            "rule": v.rule,
            "expected": v.expected,
            "observed": v.observed,
            "failed_agent": v.failed_agent,
            "failed_step": v.failed_step,
        }
        for v in violations
    ]


def _severity_summary(violations: list[Violation]) -> dict:
    counts = {"high": 0, "medium": 0, "low": 0}
    for v in violations:
        counts[v.severity] = counts.get(v.severity, 0) + 1
    return counts


def _repair_patches(repair_out: dict) -> list[dict]:
    patches = repair_out.get("patches")
    if isinstance(patches, list):
        return patches
    if repair_out.get("repair_patch"):
        return [
            {
                "repair_patch": repair_out.get("repair_patch", ""),
                "affected_primitive": repair_out.get("affected_primitive", ""),
                "patch_code": repair_out.get("patch_code", ""),
                "expected_impact": repair_out.get("expected_impact", ""),
                "confidence": repair_out.get("confidence", 0.0),
            }
        ]
    return []


def _ask_llm_for_narrative(report_core: dict) -> str:
    narrator = ConversableAgent(
        name="ReporterAgent",
        llm_config=get_llm_config(),
        system_message=(
            "You write concise judge-facing narratives for AG2 contract "
            "violation reports. Summarize what broke, who was responsible, "
            "what the fix is, and whether the regression test passed. "
            "Two short paragraphs maximum, plain text."
        ),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )
    proxy = _make_proxy("ReporterProxy")
    prompt = (
        "Write a two-paragraph operator narrative for this Contract Violation "
        "Report. No JSON, no markdown headers — plain text only.\n\n"
        f"{json.dumps(report_core, indent=2, default=str)}"
    )
    result = proxy.initiate_chat(narrator, message=prompt, max_turns=1)
    return result.chat_history[-1]["content"].strip()


async def run_reporter(
    run_trace: RunTrace,
    violations: list[Violation],
    attribution_out: dict,
    repair_out: dict,
    regression_out: dict,
    context_snapshot: ContextSnapshot | None = None,
    approval_status: str = "pending",
) -> dict:
    """Assemble the final Contract Violation Report."""
    violation_dicts = _violations_to_dicts(violations)

    report_core = {
        "run_id": run_trace.run_id,
        "workflow_name": run_trace.workflow_name,
        "violation_count": len(violations),
        "severity_summary": _severity_summary(violations),
        "failed_agent": attribution_out.get("failed_agent", ""),
        "failed_step": attribution_out.get("failed_step", -1),
        "likely_root_cause": attribution_out.get("likely_root_cause", ""),
        "repair_patch": repair_out.get("repair_patch", ""),
        "affected_primitive": repair_out.get("affected_primitive", ""),
        "patch_code": repair_out.get("patch_code", ""),
        "regression_test_status": regression_out.get("test_status", "error"),
        "repair_confidence": repair_out.get("confidence", 0.0),
        "approval_status": approval_status,
        "violations": violation_dicts,
        "patches": _repair_patches(repair_out),
    }

    try:
        narrative = _ask_llm_for_narrative(report_core)
    except Exception:
        narrative = (
            f"{report_core['workflow_name']} run {report_core['run_id']} broke "
            f"{report_core['violation_count']} contract(s). "
            f"{report_core['failed_agent']} (step {report_core['failed_step']}) "
            f"is the failed primitive. Recommended repair: "
            f"{report_core['repair_patch']}. Regression test status: "
            f"{report_core['regression_test_status']}."
        )

    report = dict(report_core)
    report["narrative"] = narrative
    return {"report": report}


if __name__ == "__main__":
    from pathlib import Path
    from zone_b.agents.trace_collector import run_trace_collector
    from zone_b.agents.contract_checker import run_contract_checker
    from zone_b.agents.attribution import run_attribution
    from zone_b.agents.repair import run_repair
    from zone_b.agents.regression_test import run_regression_test

    raw = json.loads(Path("zone_b/fixtures/sample_trace.json").read_text())

    async def _test():
        collected = await run_trace_collector(raw)
        checked = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        attributed = await run_attribution(
            checked["violations"], collected["run_trace"], collected["context_snapshot"]
        )
        repaired = await run_repair(
            checked["violations"], attributed["failed_agent"], attributed["failed_step"]
        )
        tested = await run_regression_test(
            repaired["repair_patch"], checked["violations"], collected["run_trace"]
        )
        reported = await run_reporter(
            collected["run_trace"], checked["violations"], attributed,
            repaired, tested, collected["context_snapshot"]
        )
        r = reported["report"]
        print(f"\nrun_id              : {r['run_id']}")
        print(f"violation_count     : {r['violation_count']}")
        print(f"failed_agent        : {r['failed_agent']}")
        print(f"affected_primitive  : {r['affected_primitive']}")
        print(f"regression_status   : {r['regression_test_status']}")
        print(f"repair_confidence   : {r['repair_confidence']}")
        print(f"\nnarrative:\n{r['narrative']}")

    asyncio.run(_test())
