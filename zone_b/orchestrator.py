"""Zone B diagnostic orchestrator.

Wires the six Zone B agents together in dependency order:
    TraceCollector -> ContractChecker -> Attribution -> Repair
        -> RegressionTest -> Reporter -> HumanGate

Sequential rather than a literal AG2 GroupChat: each agent is a
typed-input/typed-output transform, so a function pipeline gives
deterministic data flow and is what the issue's test code expects.
A round_robin GroupChat shim can be added on top if a chat-style
demo of the diagnostic flow is desired.
"""
import asyncio
import json
from pathlib import Path

from zone_b.agents.trace_collector import run_trace_collector
from zone_b.agents.contract_checker import run_contract_checker
from zone_b.agents.attribution import run_attribution
from zone_b.agents.repair import run_repair
from zone_b.agents.regression_test import run_regression_test
from zone_b.agents.reporter import run_reporter
from zone_b.agents.human_gate import run_human_gate


async def run_diagnostic_pipeline(trace_path: str) -> dict:
    """Run the full Zone B diagnostic pipeline and return the final report."""
    raw = json.loads(Path(trace_path).read_text())

    print(f"\n[1/7] TraceCollector — loading {trace_path}")
    collected = await run_trace_collector(raw)
    print(f"      {collected['summary']}")

    print(f"\n[2/7] ContractChecker — applying contracts")
    checked = run_contract_checker(
        collected["run_trace"], collected["context_snapshot"]
    )
    print(f"      {checked['violation_count']} violation(s) found")

    print(f"\n[3/7] Attribution — identifying failed agent")
    attributed = await run_attribution(
        checked["violations"], collected["run_trace"], collected["context_snapshot"]
    )
    print(
        f"      failed_agent={attributed['failed_agent']} "
        f"step={attributed['failed_step']}"
    )

    print(f"\n[4/7] Repair — mapping to AG2 primitive")
    repaired = await run_repair(
        checked["violations"], attributed["failed_agent"], attributed["failed_step"]
    )
    print(
        f"      affected_primitive={repaired['affected_primitive']} "
        f"confidence={repaired['confidence']:.2f}"
    )

    print(f"\n[5/7] RegressionTest — running in Daytona")
    tested = await run_regression_test(
        repaired["repair_patch"], checked["violations"], collected["run_trace"]
    )
    print(
        f"      test_status={tested['test_status']} "
        f"sandbox={tested['sandbox_id']}"
    )

    print(f"\n[6/7] Reporter — assembling Contract Violation Report")
    reported = await run_reporter(
        collected["run_trace"],
        checked["violations"],
        attributed,
        repaired,
        tested,
        collected["context_snapshot"],
    )
    report = reported["report"]

    print(f"\n[7/7] HumanGate — approval check")
    gate = await run_human_gate(report)
    report["approval_status"] = gate["approval_status"]
    report["approval_comments"] = gate["comments"]

    return report


def _print_final_report(report: dict) -> None:
    print("\n" + "=" * 60)
    print("CONTRACT VIOLATION REPORT")
    print("=" * 60)
    print(f"Run ID            : {report['run_id']}")
    print(f"Workflow          : {report['workflow_name']}")
    print(f"Violation count   : {report['violation_count']}")
    print(f"Severity summary  : {report['severity_summary']}")
    print(f"Failed agent      : {report['failed_agent']} (step {report['failed_step']})")
    print(f"Likely root cause : {report['likely_root_cause']}")
    print(f"Affected primitive: {report['affected_primitive']}")
    print(f"Repair patch      : {report['repair_patch']}")
    print(f"Repair confidence : {report['repair_confidence']:.2f}")
    print(f"Regression status : {report['regression_test_status']}")
    print(f"Approval status   : {report['approval_status']}")
    print(f"\nNarrative:\n{report['narrative']}")
    print("=" * 60)


if __name__ == "__main__":
    report = asyncio.run(
        run_diagnostic_pipeline("zone_b/fixtures/sample_trace.json")
    )
    _print_final_report(report)
