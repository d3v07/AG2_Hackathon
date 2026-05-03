"""Attribution — identifies the agent and step responsible for each violation.

Per issue #2: input is violations + run_trace + context_snapshot. Uses a
ConversableAgent to reason over the handoff path and per-violation
metadata, returns failed_agent / failed_step / likely_root_cause /
attributions[]. Falls back to deterministic derivation if the LLM
response cannot be parsed.
"""
import asyncio
import json
from autogen import ConversableAgent, UserProxyAgent
from shared.models import RunTrace, ContextSnapshot, Violation
from zone_b.config import get_llm_config


def _parse_json_body(body: str) -> dict:
    """Strip ```json fences and parse. Raises on failure."""
    body = body.strip()
    if body.startswith("```"):
        body = body.split("```")[1]
        if body.startswith("json"):
            body = body[4:]
    return json.loads(body)


def _deterministic_failed_step(run_trace: RunTrace, agent_name: str) -> int:
    for e in run_trace.events:
        if e.agent == agent_name:
            return e.step
    return -1


def _ask_llm_for_attribution(
    violations: list[Violation],
    run_trace: RunTrace,
    context_snapshot: ContextSnapshot,
) -> dict:
    """Single-turn ConversableAgent call returning JSON attribution."""
    attributor = ConversableAgent(
        name="AttributionAgent",
        llm_config=get_llm_config(),
        system_message=(
            "You are a multi-agent failure attribution analyst. Given violations "
            "and a workflow trace, identify which agent is responsible for each "
            "violation and explain the root cause. Reply with a JSON object only."
        ),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )
    proxy = UserProxyAgent(
        name="AttributionProxy",
        llm_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: True,
        max_consecutive_auto_reply=0,
        code_execution_config=False,
    )

    handoff_path = [e.agent for e in run_trace.events]
    violations_summary = [
        {
            "type": v.contract_type,
            "rule": v.rule,
            "failed_agent": v.failed_agent,
            "failed_step": v.failed_step,
        }
        for v in violations
    ]
    prompt = (
        f"Workflow handoff path: {handoff_path}\n"
        f"verified_sources_count: {context_snapshot.verified_sources_count}\n"
        f"approval_status: {context_snapshot.approval_status}\n"
        f"tool_events recorded: {len(context_snapshot.tool_events)}\n"
        f"Violations: {json.dumps(violations_summary)}\n\n"
        "Reply with ONLY a JSON object with keys:\n"
        '  "failed_agent": single agent name most responsible overall\n'
        '  "failed_step": int step number where the failure became visible\n'
        '  "likely_root_cause": one-sentence explanation\n'
        '  "attributions": list of {"violation_type", "agent", "step", "evidence"}\n'
        "No prose outside the JSON."
    )
    result = proxy.initiate_chat(attributor, message=prompt, max_turns=1)
    body = result.chat_history[-1]["content"]
    return _parse_json_body(body)


async def run_attribution(
    violations: list[Violation],
    run_trace: RunTrace,
    context_snapshot: ContextSnapshot,
) -> dict:
    """Identify failed agent + step + root cause for the given violations."""
    if not violations:
        return {
            "failed_agent": "",
            "failed_step": -1,
            "likely_root_cause": "no violations detected",
            "attributions": [],
        }

    try:
        data = _ask_llm_for_attribution(violations, run_trace, context_snapshot)
        return {
            "failed_agent": data.get("failed_agent", violations[0].failed_agent),
            "failed_step": int(data.get("failed_step", violations[0].failed_step)),
            "likely_root_cause": data.get(
                "likely_root_cause", "contract check failed without explanation"
            ),
            "attributions": data.get("attributions", []),
        }
    except Exception:
        primary = violations[0]
        return {
            "failed_agent": primary.failed_agent,
            "failed_step": _deterministic_failed_step(run_trace, primary.failed_agent),
            "likely_root_cause": (
                f"{primary.failed_agent} violated {primary.contract_type} contract: "
                f"{primary.rule}"
            ),
            "attributions": [
                {
                    "violation_type": v.contract_type,
                    "agent": v.failed_agent,
                    "step": v.failed_step,
                    "evidence": v.observed,
                }
                for v in violations
            ],
        }


if __name__ == "__main__":
    from pathlib import Path
    from zone_b.agents.trace_collector import run_trace_collector
    from zone_b.agents.contract_checker import run_contract_checker

    raw = json.loads(Path("zone_b/fixtures/sample_trace.json").read_text())

    async def _test():
        collected = await run_trace_collector(raw)
        checked = run_contract_checker(
            collected["run_trace"], collected["context_snapshot"]
        )
        attributed = await run_attribution(
            checked["violations"], collected["run_trace"], collected["context_snapshot"]
        )
        print(f"\nfailed_agent       : {attributed['failed_agent']}")
        print(f"failed_step        : {attributed['failed_step']}")
        print(f"likely_root_cause  : {attributed['likely_root_cause']}")
        print(f"attributions count : {len(attributed['attributions'])}")
        for a in attributed["attributions"]:
            print(f"  - {a}")

    asyncio.run(_test())
