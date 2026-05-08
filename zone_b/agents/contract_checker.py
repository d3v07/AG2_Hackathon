import asyncio
from autogen import ConversableAgent
from shared.models import RunTrace, ContextSnapshot, Violation
from zone_b.contracts import DEFAULT_CONTRACTS
from zone_b.contracts.checks import (
    check_routing_contract,
    check_schema_contract,
)
from zone_b.config import get_llm_config
from zone_b.utils import parse_json_body as _parse_json_body, make_proxy as _make_proxy


CONTRACTS = DEFAULT_CONTRACTS


def _check_routing_contract(run_trace: RunTrace) -> bool:
    return check_routing_contract(run_trace, None)


def _check_schema_contract(snap: ContextSnapshot) -> bool:
    return check_schema_contract(None, snap)


def _find_failed_step(run_trace: RunTrace, agent_name: str) -> int:
    for e in run_trace.events:
        if e.agent == agent_name:
            return e.step
    return -1


def _generate_violation_text(contract: dict, run_trace: RunTrace, snap: ContextSnapshot) -> tuple[str, str]:
    """Use ConversableAgent to generate human-readable expected/observed strings."""
    try:
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
        data = _parse_json_body(result.chat_history[-1]["content"])
        return data.get("expected", contract["rule"]), data.get("observed", "contract check failed")
    except Exception:
        return contract["rule"], "contract check failed"


def _find_matching_span_id(
    spans: list[dict] | None,
    failed_agent: str,
    failed_step: int,
) -> str | None:
    """Find the span that owns this violation, by step then by agent.
    Returns None when spans aren't available (legacy raw_trace) so the
    forensic UI link gracefully falls back to step+agent attribution."""
    if not spans:
        return None
    # Prefer step-based match if any span carries concord.step in attributes
    for span in spans:
        attrs = span.get("attributes") or {}
        if attrs.get("concord.step") == failed_step and span.get("agent") == failed_agent:
            return span.get("span_id")
    # Fallback: first span whose agent matches
    for span in spans:
        if span.get("agent") == failed_agent:
            return span.get("span_id")
    return None


def run_contract_checker(
    run_trace: RunTrace,
    context_snapshot: ContextSnapshot,
    spans: list[dict] | None = None,
) -> dict:
    """Check all contracts and return list of Violation objects.

    When ``spans`` is provided (Sprint 15 #75), each violation gets its
    ``span_id`` stamped so the forensic UI can deep-link from a violation
    to the offending span. Legacy callers without spans are unaffected —
    ``span_id`` stays None.
    """
    violations: list[Violation] = []

    for contract in CONTRACTS:
        passed = contract["check"](run_trace, context_snapshot)
        if not passed:
            expected, observed = _generate_violation_text(contract, run_trace, context_snapshot)
            failed_step = _find_failed_step(run_trace, contract["failed_agent"])
            span_id = _find_matching_span_id(spans, contract["failed_agent"], failed_step)
            violations.append(Violation(
                contract_type=contract["type"],
                severity=contract["severity"],
                rule=contract["rule"],
                expected=expected,
                observed=observed,
                failed_agent=contract["failed_agent"],
                failed_step=failed_step,
                span_id=span_id,
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
