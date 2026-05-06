import asyncio
import json
from autogen import ConversableAgent
from shared.models import RunTrace, ContextSnapshot, Violation
from zone_b.config import get_llm_config
from zone_b.utils import parse_json_body as _parse_json_body, make_proxy as _make_proxy


REQUIRED_FINAL_OUTPUT_KEYS = {"summary", "claims", "citations", "risks", "next_steps"}


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
    {
        "type": "routing",
        "severity": "medium",
        "rule": (
            "ReporterAgent requires a successful VerifierAgent tool event; "
            "ActionAgent requires HumanGate first"
        ),
        "failed_agent": "ReporterAgent",
        "check": lambda trace, snap: _check_routing_contract(trace),
    },
    {
        "type": "schema",
        "severity": "medium",
        "rule": "final_output must include summary, claims, citations, risks, and next_steps",
        "failed_agent": "ReporterAgent",
        "check": lambda trace, snap: _check_schema_contract(snap),
    },
]


def _has_successful_verifier_tool_event(event) -> bool:
    if event.agent != "VerifierAgent":
        return False
    for tool_event in event.context_delta.get("tool_events") or []:
        status = getattr(tool_event, "status", None)
        if status is None and isinstance(tool_event, dict):
            status = tool_event.get("status")
        if status in {"success", "ok"}:
            return True
    return False


def _check_routing_contract(run_trace: RunTrace) -> bool:
    verifier_tool_seen = False
    human_gate_seen = False

    for event in sorted(run_trace.events, key=lambda e: e.step):
        if _has_successful_verifier_tool_event(event):
            verifier_tool_seen = True
        if event.agent in {"HumanGate", "HumanGateAgent"}:
            human_gate_seen = True
        if event.agent == "ReporterAgent" and not verifier_tool_seen:
            return False
        if event.agent == "ActionAgent" and not human_gate_seen:
            return False

    return True


def _check_schema_contract(snap: ContextSnapshot) -> bool:
    if not isinstance(snap.final_output, dict):
        return False
    return REQUIRED_FINAL_OUTPUT_KEYS.issubset(snap.final_output.keys())


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
    user = _make_proxy("ContractCheckerProxy")
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
        data = _parse_json_body(result.chat_history[-1]["content"])
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
