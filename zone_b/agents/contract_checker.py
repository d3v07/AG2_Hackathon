import asyncio
import json
from autogen import ConversableAgent, UserProxyAgent
from shared.models import RunTrace, ContextSnapshot, Violation
from zone_b.config import get_llm_config


CONTRACTS = [
    {
        "type": "evidence",
        "severity": "high",
        "rule": "verified_sources_count must be > 0 before ReporterAgent runs",
        "failed_agent": "VerifierAgent",
        "check": lambda trace, snap: snap.verified_sources_count > 0,
    },
    {
        "type": "tool",
        "severity": "high",
        "rule": "VerifierAgent must record a tool_call_id (Tavily or Daytona)",
        "failed_agent": "VerifierAgent",
        "check": lambda trace, snap: any(
            e.agent == "VerifierAgent" and e.tool_call_id for e in trace.events
        ),
    },
    {
        "type": "approval",
        "severity": "high",
        "rule": "ActionAgent requires approval_status == approved before running",
        "failed_agent": "ActionAgent",
        "check": lambda trace, snap: snap.approval_status == "approved",
    },
]


def _find_failed_step(run_trace: RunTrace, agent_name: str) -> int:
    for e in run_trace.events:
        if e.agent == agent_name:
            return e.step
    return -1


def _generate_violation_text(contract: dict, run_trace: RunTrace, snap: ContextSnapshot) -> tuple[str, str]:
    """Use ConversableAgent to generate human-readable expected/observed strings."""
    checker = ConversableAgent(
        name="ContractCheckerAgent",
        llm_config=get_llm_config(),
        system_message=(
            "You are a contract violation analyst for AG2 multi-agent workflows. "
            "When given a contract violation, return ONLY a JSON object with keys "
            "'expected' and 'observed' — one sentence each. No other text."
        ),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
    )
    user = UserProxyAgent(
        name="ContractCheckerProxy",
        llm_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: True,
        max_consecutive_auto_reply=0,
        code_execution_config=False,
    )
    prompt = (
        f"Contract type: {contract['type']}\n"
        f"Rule: {contract['rule']}\n"
        f"Context: verified_sources_count={snap.verified_sources_count}, "
        f"approval_status={snap.approval_status}, "
        f"handoff_path={[e.agent for e in run_trace.events]}\n"
        f"Return JSON with 'expected' and 'observed' keys only."
    )
    result = user.initiate_chat(checker, message=prompt, max_turns=1)
    try:
        body = result.chat_history[-1]["content"].strip()
        if body.startswith("```"):
            body = body.split("```")[1]
            if body.startswith("json"):
                body = body[4:]
        data = json.loads(body)
        return data.get("expected", contract["rule"]), data.get("observed", "contract check failed")
    except Exception:
        return contract["rule"], "contract check failed"


def run_contract_checker(run_trace: RunTrace, context_snapshot: ContextSnapshot) -> dict:
    """Check all contracts and return list of Violation objects."""
    violations: list[Violation] = []

    for contract in CONTRACTS:
        passed = contract["check"](run_trace, context_snapshot)
        if not passed:
            expected, observed = _generate_violation_text(contract, run_trace, context_snapshot)
            failed_step = _find_failed_step(run_trace, contract["failed_agent"])
            violations.append(Violation(
                contract_type=contract["type"],
                severity=contract["severity"],
                rule=contract["rule"],
                expected=expected,
                observed=observed,
                failed_agent=contract["failed_agent"],
                failed_step=failed_step,
            ))

    severity_summary = {"high": 0, "medium": 0, "low": 0}
    for v in violations:
        severity_summary[v.severity] += 1

    return {
        "violations": violations,
        "violation_count": len(violations),
        "severity_summary": severity_summary,
    }


if __name__ == "__main__":
    import json
    from pathlib import Path
    from zone_b.agents.trace_collector import run_trace_collector

    raw = json.loads(Path("zone_b/fixtures/sample_trace.json").read_text())

    async def _test():
        collected = await run_trace_collector(raw)
        result = run_contract_checker(collected["run_trace"], collected["context_snapshot"])
        print(f"Violations found: {result['violation_count']}")
        for v in result["violations"]:
            print(f"  [{v.severity.upper()}] {v.contract_type}: {v.rule}")

    asyncio.run(_test())
