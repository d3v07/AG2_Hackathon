import asyncio
import json
from autogen.beta import Agent
from shared.models import RunTrace, ContextSnapshot, Violation
from zone_b.config import get_config


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
    """Return step number of the first event for the given agent."""
    for e in run_trace.events:
        if e.agent == agent_name:
            return e.step
    return -1


async def _generate_violation_text(contract: dict, run_trace: RunTrace, snap: ContextSnapshot) -> tuple[str, str]:
    """Use LLM to generate human-readable expected and observed strings."""
    agent = Agent(config=get_config(), name="ContractCheckerAgent")
    prompt = (
        f"A contract violation was detected.\n"
        f"Contract type: {contract['type']}\n"
        f"Rule: {contract['rule']}\n"
        f"Context: verified_sources_count={snap.verified_sources_count}, "
        f"approval_status={snap.approval_status}, "
        f"handoff_path={[e.agent for e in run_trace.events]}\n\n"
        f"Reply with a JSON object with exactly two keys:\n"
        f"  \"expected\": one sentence describing what should have happened\n"
        f"  \"observed\": one sentence describing what actually happened\n"
        f"Reply with only the JSON object, no other text."
    )
    reply = await agent.ask(prompt)
    try:
        body = reply.body.strip()
        # strip markdown code fences if present
        if body.startswith("```"):
            body = body.split("```")[1]
            if body.startswith("json"):
                body = body[4:]
        data = json.loads(body)
        return data.get("expected", contract["rule"]), data.get("observed", "contract check failed")
    except Exception:
        return contract["rule"], "contract check failed"


async def run_contract_checker(run_trace: RunTrace, context_snapshot: ContextSnapshot) -> dict:
    """Check all contracts and return list of Violation objects."""
    violations: list[Violation] = []

    for contract in CONTRACTS:
        passed = contract["check"](run_trace, context_snapshot)
        if not passed:
            expected, observed = await _generate_violation_text(contract, run_trace, context_snapshot)
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
        result = await run_contract_checker(collected["run_trace"], collected["context_snapshot"])
        print(f"Violations found: {result['violation_count']}")
        for v in result["violations"]:
            print(f"  [{v.severity.upper()}] {v.contract_type}: {v.rule}")
            print(f"    expected : {v.expected}")
            print(f"    observed : {v.observed}")

    asyncio.run(_test())
