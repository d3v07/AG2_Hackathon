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

from autogen import ConversableAgent

from zone_b.agents.trace_collector import run_trace_collector
from zone_b.agents.contract_checker import run_contract_checker
from zone_b.agents.attribution import run_attribution
from zone_b.agents.repair import run_repair
from zone_b.agents.regression_test import run_regression_test
from zone_b.agents.reporter import run_reporter
from zone_b.agents.human_gate import run_human_gate

MAX_REPAIR_ITERATIONS = 3


def _zero_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _zero_cost() -> dict[str, float | int]:
    return {
        "daytona_seconds": 0,
        "llm_tokens": 0,
        "llm_cost_usd": 0,
        "daytona_cost_usd": 0,
    }


def _aggregate_regression_attempts(attempts: list[dict]) -> dict:
    if not attempts:
        return {}
    final = dict(attempts[-1])
    usage = _zero_usage()
    cost = _zero_cost()
    duration_ms = 0
    for attempt in attempts:
        duration_ms += int(attempt.get("duration_ms", 0) or 0)
        attempt_usage = attempt.get("usage") if isinstance(attempt.get("usage"), dict) else {}
        usage["prompt_tokens"] += int(attempt_usage.get("prompt_tokens", 0) or 0)
        usage["completion_tokens"] += int(attempt_usage.get("completion_tokens", 0) or 0)
        usage["total_tokens"] += int(attempt_usage.get("total_tokens", 0) or 0)
        attempt_cost = attempt.get("cost") if isinstance(attempt.get("cost"), dict) else {}
        cost["daytona_seconds"] = round(
            float(cost["daytona_seconds"]) + float(attempt_cost.get("daytona_seconds", 0) or 0),
            3,
        )
        cost["llm_tokens"] = int(cost["llm_tokens"]) + int(
            attempt_cost.get("llm_tokens", attempt_usage.get("total_tokens", 0)) or 0
        )
        cost["llm_cost_usd"] = round(
            float(cost["llm_cost_usd"]) + float(attempt_cost.get("llm_cost_usd", 0) or 0),
            8,
        )
        cost["daytona_cost_usd"] = round(
            float(cost["daytona_cost_usd"]) + float(attempt_cost.get("daytona_cost_usd", 0) or 0),
            8,
        )
    final["duration_ms"] = duration_ms
    final["usage"] = usage
    final["cost"] = cost
    final["regression_attempts"] = attempts
    return final


def _register_repair_regression_nested_chat() -> ConversableAgent:
    coordinator = ConversableAgent(
        name="RepairIterationCoordinator",
        llm_config=False,
        human_input_mode="NEVER",
        code_execution_config=False,
    )
    regression_agent = ConversableAgent(
        name="RegressionIterationAgent",
        llm_config=False,
        human_input_mode="NEVER",
        code_execution_config=False,
    )
    coordinator.register_nested_chats(
        [
            {
                "recipient": regression_agent,
                "message": "Run the latest repair patch through regression.",
                "max_turns": 1,
                "summary_method": "last_msg",
            }
        ],
        trigger=lambda _sender: True,
        reply_func_from_nested_chats=lambda *_args, **_kwargs: (
            True,
            "repair-regression cycle",
        ),
    )
    return coordinator


async def run_repair_test_iterations(
    violations,
    run_trace,
    failed_agent: str,
    failed_step: int,
    *,
    repair_func=run_repair,
    regression_func=run_regression_test,
    max_iterations: int = MAX_REPAIR_ITERATIONS,
) -> dict:
    """Run Repair -> RegressionTest until pass, non-retryable error, or cap."""
    _register_repair_regression_nested_chat()
    repaired = {}
    tested = {}
    regression_attempts = []
    iteration_count = 0
    for iteration in range(1, max(1, max_iterations) + 1):
        iteration_count = iteration
        repaired = await repair_func(violations, failed_agent, failed_step)
        tested = await regression_func(
            repaired.get("repair_patch", ""), violations, run_trace
        )
        regression_attempts.append(tested)
        if tested.get("test_status") != "fail":
            break
    tested = _aggregate_regression_attempts(regression_attempts)
    return {
        "repair": repaired,
        "regression": tested,
        "iteration_count": iteration_count,
    }


async def run_diagnostic_pipeline(trace_path: str) -> dict:
    """Run the full Zone B diagnostic pipeline and return the final report."""
    raw = json.loads(Path(trace_path).read_text())

    print(f"\n[1/7] TraceCollector — loading {trace_path}")
    collected = await run_trace_collector(raw)
    print(f"      {collected['summary']}")

    print("\n[2/7] ContractChecker — applying contracts")
    checked = run_contract_checker(
        collected["run_trace"], collected["context_snapshot"]
    )
    print(f"      {checked['violation_count']} violation(s) found")

    print("\n[3/7] Attribution — identifying failed agent")
    attributed = await run_attribution(
        checked["violations"], collected["run_trace"], collected["context_snapshot"]
    )
    print(
        f"      failed_agent={attributed['failed_agent']} "
        f"step={attributed['failed_step']}"
    )

    print("\n[4/7] Repair/Test — iterating patch through regression")
    iteration = await run_repair_test_iterations(
        checked["violations"],
        collected["run_trace"],
        attributed["failed_agent"],
        attributed["failed_step"],
    )
    repaired = iteration["repair"]
    tested = iteration["regression"]
    iteration_count = iteration["iteration_count"]
    print(
        f"      affected_primitive={repaired['affected_primitive']} "
        f"confidence={repaired['confidence']:.2f} "
        f"iterations={iteration_count}"
    )

    print("\n[5/7] RegressionTest — completed in Daytona")
    print(
        f"      test_status={tested['test_status']} "
        f"sandbox={tested['sandbox_id']}"
    )
    summary = tested.get("per_violation_summary", {})
    if summary:
        print(
            "      per_violation="
            f"{summary.get('pass', 0)} pass/"
            f"{summary.get('fail', 0)} fail/"
            f"{summary.get('error', 0)} error"
        )

    print("\n[6/7] Reporter — assembling Contract Violation Report")
    reported = await run_reporter(
        collected["run_trace"],
        checked["violations"],
        attributed,
        repaired,
        tested,
        collected["context_snapshot"],
        iteration_count=iteration_count,
    )
    report = reported["report"]

    print("\n[7/7] HumanGate — approval check")
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
    print(f"Repair patches    : {len(report.get('patches', []))}")
    print(f"Repair confidence : {report['repair_confidence']:.2f}")
    print(f"Iteration count   : {report.get('iteration_count', 1)}")
    print(f"Regression status : {report['regression_test_status']}")
    regression_summary = report.get("regression_summary", {})
    if regression_summary:
        print(
            "Regression tests  : "
            f"{regression_summary.get('pass', 0)} pass / "
            f"{regression_summary.get('fail', 0)} fail / "
            f"{regression_summary.get('error', 0)} error"
        )
    print(f"Approval status   : {report['approval_status']}")
    print(f"\nNarrative:\n{report['narrative']}")
    print("=" * 60)


if __name__ == "__main__":
    report = asyncio.run(
        run_diagnostic_pipeline("zone_b/fixtures/sample_trace.json")
    )
    _print_final_report(report)
