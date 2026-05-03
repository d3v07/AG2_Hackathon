"""Zone B AG2 GroupChat — RoundRobinPattern over the 7 diagnostic stages.

The legacy zone_b/orchestrator.py is a sequential async pipeline kept for
backward-compat with the existing test suite and the --fixture flag. This
module wraps the same stage logic in a true AG2 RoundRobinPattern, with
ContextVariables threading state between stages.

Each stage is a ConversableAgent with llm_config=False and a custom
async reply handler that:
  1. reads its inputs from ContextVariables,
  2. runs the underlying logic (the existing zone_b.agents.* functions),
  3. writes its outputs back to ContextVariables,
  4. returns a one-line status message that becomes the next round's
     visible chat content.

After the round-robin completes, the assembled report is read out of
ContextVariables and returned.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from autogen import ConversableAgent
from autogen.agentchat.group import (
    ContextVariables,
    TerminateTarget,
)
from autogen.agentchat.group.multi_agent_chat import a_initiate_group_chat
from autogen.agentchat.group.patterns import RoundRobinPattern

from zone_b.agents.attribution import run_attribution
from zone_b.agents.contract_checker import run_contract_checker
from zone_b.agents.human_gate import run_human_gate
from zone_b.agents.regression_test import run_regression_test
from zone_b.agents.repair import run_repair
from zone_b.agents.reporter import run_reporter
from zone_b.agents.trace_collector import run_trace_collector


_STAGE_NAMES = [
    "TraceCollector",
    "ContractChecker",
    "Attribution",
    "Repair",
    "RegressionTest",
    "Reporter",
    "HumanGate",
]


async def _trace_collector_stage(ctx: ContextVariables) -> str:
    raw = ctx.get("raw_trace")
    if raw is None:
        return "TraceCollector: missing raw_trace"
    collected = await run_trace_collector(raw)
    ctx.set("run_trace", collected["run_trace"])
    ctx.set("context_snapshot", collected["context_snapshot"])
    ctx.set("handoff_path", collected["handoff_path"])
    ctx.set("collector_summary", collected["summary"])
    return f"TraceCollector: {collected['summary']}"


async def _contract_checker_stage(ctx: ContextVariables) -> str:
    run_trace = ctx.get("run_trace")
    snap = ctx.get("context_snapshot")
    if run_trace is None or snap is None:
        return "ContractChecker: missing inputs"
    checked = run_contract_checker(run_trace, snap)
    ctx.set("violations", checked["violations"])
    ctx.set("violation_count", checked["violation_count"])
    ctx.set("severity_summary", checked["severity_summary"])
    return f"ContractChecker: {checked['violation_count']} violation(s)"


async def _attribution_stage(ctx: ContextVariables) -> str:
    violations = ctx.get("violations") or []
    run_trace = ctx.get("run_trace")
    snap = ctx.get("context_snapshot")
    if run_trace is None or snap is None:
        return "Attribution: missing inputs"
    attributed = await run_attribution(violations, run_trace, snap)
    ctx.set("attribution", attributed)
    return (
        f"Attribution: failed_agent={attributed['failed_agent']} "
        f"step={attributed['failed_step']}"
    )


async def _repair_stage(ctx: ContextVariables) -> str:
    violations = ctx.get("violations") or []
    attribution = ctx.get("attribution") or {}
    repaired = await run_repair(
        violations,
        attribution.get("failed_agent", ""),
        attribution.get("failed_step", -1),
    )
    ctx.set("repair", repaired)
    return (
        f"Repair: primitive={repaired['affected_primitive']} "
        f"confidence={repaired['confidence']:.2f}"
    )


async def _regression_test_stage(ctx: ContextVariables) -> str:
    repair = ctx.get("repair") or {}
    violations = ctx.get("violations") or []
    run_trace = ctx.get("run_trace")
    if run_trace is None:
        return "RegressionTest: missing run_trace"
    tested = await run_regression_test(
        repair.get("repair_patch", ""), violations, run_trace
    )
    ctx.set("regression", tested)
    return (
        f"RegressionTest: status={tested['test_status']} "
        f"sandbox={tested['sandbox_id']}"
    )


async def _reporter_stage(ctx: ContextVariables) -> str:
    run_trace = ctx.get("run_trace")
    snap = ctx.get("context_snapshot")
    if run_trace is None or snap is None:
        return "Reporter: missing inputs"
    violations = ctx.get("violations") or []
    attribution = ctx.get("attribution") or {}
    repair = ctx.get("repair") or {}
    regression = ctx.get("regression") or {}
    reported = await run_reporter(
        run_trace, violations, attribution, repair, regression, snap
    )
    ctx.set("report", reported["report"])
    return f"Reporter: report assembled with {len(violations)} violation(s)"


async def _human_gate_stage(ctx: ContextVariables) -> str:
    report = ctx.get("report") or {}
    interactive = bool(ctx.get("interactive"))
    gate = await run_human_gate(report, interactive=interactive)
    report["approval_status"] = gate["approval_status"]
    report["approval_comments"] = gate.get("comments", "")
    ctx.set("report", report)
    ctx.set("approval_status", gate["approval_status"])
    return f"HumanGate: approval_status={gate['approval_status']}"


_STAGE_FNS = {
    "TraceCollector": _trace_collector_stage,
    "ContractChecker": _contract_checker_stage,
    "Attribution": _attribution_stage,
    "Repair": _repair_stage,
    "RegressionTest": _regression_test_stage,
    "Reporter": _reporter_stage,
    "HumanGate": _human_gate_stage,
}


def _make_stage_agent(name: str, ctx: ContextVariables) -> ConversableAgent:
    """Wrap a stage function as a ConversableAgent with a custom reply.

    The agent has llm_config=False — no LLM call. Its reply is the result
    of running the stage's pure-Python logic against the shared ctx.
    """
    agent = ConversableAgent(
        name=name,
        llm_config=False,
        human_input_mode="NEVER",
        code_execution_config=False,
    )
    stage_fn = _STAGE_FNS[name]

    async def _reply(
        recipient: Any = None,
        messages: Any = None,
        sender: Any = None,
        config: Any = None,
    ) -> tuple[bool, str]:
        msg = await stage_fn(ctx)
        return True, msg

    agent.register_reply(
        trigger=[ConversableAgent, None],
        reply_func=_reply,
        remove_other_reply_funcs=True,
    )
    return agent


def build_zone_b_stages(
    raw_trace: dict[str, Any], interactive: bool = False
) -> tuple[list[ConversableAgent], ContextVariables]:
    """Construct the 7-stage Zone B group chat.

    Returns the agent list (in round-robin order) and the initial
    ContextVariables with the raw trace and interactive flag bound.
    """
    ctx = ContextVariables(
        data={
            "raw_trace": raw_trace,
            "interactive": interactive,
            "run_trace": None,
            "context_snapshot": None,
            "violations": [],
            "violation_count": 0,
            "attribution": {},
            "repair": {},
            "regression": {},
            "report": {},
            "approval_status": "pending",
        }
    )
    agents = [_make_stage_agent(name, ctx) for name in _STAGE_NAMES]
    return agents, ctx


async def run_diagnostic_group_chat(
    trace_path: str | Path, interactive: bool = False
) -> dict[str, Any]:
    """Run the Zone B diagnostic pipeline as an AG2 RoundRobinPattern."""
    raw_trace = json.loads(Path(trace_path).read_text())
    agents, ctx = build_zone_b_stages(raw_trace, interactive=interactive)
    pattern = RoundRobinPattern(
        initial_agent=agents[0],
        agents=agents,
        context_variables=ctx,
        group_after_work=TerminateTarget(),
    )
    await a_initiate_group_chat(
        pattern=pattern,
        messages="Begin diagnostic over the supplied run trace.",
        max_rounds=len(agents) + 1,
    )
    report = ctx.get("report") or {}
    return report


if __name__ == "__main__":
    report = asyncio.run(
        run_diagnostic_group_chat(
            "zone_b/fixtures/sample_trace.json", interactive=False
        )
    )
    print("\n" + "=" * 60)
    print("CONTRACT VIOLATION REPORT (via Zone B GroupChat)")
    print("=" * 60)
    if not report:
        print("No report produced.")
    else:
        print(f"Run ID            : {report.get('run_id')}")
        print(f"Workflow          : {report.get('workflow_name')}")
        print(f"Violation count   : {report.get('violation_count')}")
        print(f"Severity summary  : {report.get('severity_summary')}")
        print(f"Failed agent      : {report.get('failed_agent')}")
        print(f"Approval status   : {report.get('approval_status')}")
