"""Repair — maps a violation to an AG2 primitive and proposes a patch.

Per issue #2: the violation_type → affected_primitive map is deterministic
(no LLM). A single ConversableAgent call generates the patch_code snippet
and expected_impact text. Confidence reverts to a low baseline if the LLM
cannot produce parseable JSON.
"""
import asyncio
import json
from autogen import ConversableAgent, UserProxyAgent
from shared.models import Violation
from zone_b.config import get_llm_config


PRIMITIVE_MAP: dict[str, str] = {
    "evidence": "Guardrail",
    "tool": "OnContextCondition",
    "routing": "Handoff",
    "approval": "HumanGate",
    "schema": "Guardrail",
}

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


from zone_b.utils import parse_json_body as _parse_json_body


def _pick_primary(violations: list[Violation]) -> Violation:
    """Highest severity, ties broken by first occurrence in list."""
    return max(violations, key=lambda v: SEVERITY_RANK.get(v.severity, 0))


def _ask_llm_for_patch(
    primary: Violation, primitive: str, failed_agent: str, failed_step: int
) -> dict:
    """Generate patch_code + expected_impact text via ConversableAgent."""
    repairer = ConversableAgent(
        name="RepairAgent",
        llm_config=get_llm_config(),
        system_message=(
            "You are an AG2 repair engineer. Given a violation and the AG2 "
            "primitive that should fix it, produce a short Python snippet "
            "showing how to apply that primitive in an AG2 workflow, and one "
            "sentence describing the expected impact. Reply with JSON only."
        ),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )
    proxy = UserProxyAgent(
        name="RepairProxy",
        llm_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: True,
        max_consecutive_auto_reply=0,
        code_execution_config=False,
    )
    prompt = (
        f"Violation type     : {primary.contract_type}\n"
        f"Rule               : {primary.rule}\n"
        f"Failed agent       : {failed_agent}\n"
        f"Failed step        : {failed_step}\n"
        f"Affected primitive : {primitive}\n\n"
        "Reply with ONLY a JSON object with keys:\n"
        '  "patch_code": short Python snippet using the AG2 primitive above\n'
        '  "expected_impact": one sentence describing what the patch fixes\n'
        "No prose outside the JSON."
    )
    result = proxy.initiate_chat(repairer, message=prompt, max_turns=1)
    body = result.chat_history[-1]["content"]
    return _parse_json_body(body)


async def run_repair(
    violations: list[Violation],
    failed_agent: str,
    failed_step: int,
) -> dict:
    """Map the primary violation to an AG2 primitive and generate a patch."""
    if not violations:
        return {
            "repair_patch": "no repair required",
            "affected_primitive": "",
            "patch_code": "",
            "expected_impact": "no violations to repair",
            "confidence": 0.0,
        }

    primary = _pick_primary(violations)
    primitive = PRIMITIVE_MAP.get(primary.contract_type, "Guardrail")
    repair_patch = (
        f"Add {primitive} to enforce: {primary.rule} "
        f"(failed at {failed_agent}, step {failed_step})"
    )

    try:
        data = _ask_llm_for_patch(primary, primitive, failed_agent, failed_step)
        patch_code = data.get("patch_code", "").strip() or f"# Apply {primitive}"
        expected_impact = data.get("expected_impact", "").strip() or (
            f"{primitive} prevents {primary.contract_type} contract from being violated again"
        )
        confidence = 0.85
    except Exception:
        patch_code = f"# TODO: apply {primitive} to fix {primary.contract_type} violation"
        expected_impact = (
            f"{primitive} prevents {primary.contract_type} contract from being violated again"
        )
        confidence = 0.5

    return {
        "repair_patch": repair_patch,
        "affected_primitive": primitive,
        "patch_code": patch_code,
        "expected_impact": expected_impact,
        "confidence": confidence,
    }


if __name__ == "__main__":
    from pathlib import Path
    from zone_b.agents.trace_collector import run_trace_collector
    from zone_b.agents.contract_checker import run_contract_checker
    from zone_b.agents.attribution import run_attribution

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
        print(f"\naffected_primitive : {repaired['affected_primitive']}")
        print(f"repair_patch       : {repaired['repair_patch']}")
        print(f"expected_impact    : {repaired['expected_impact']}")
        print(f"confidence         : {repaired['confidence']}")
        print(f"patch_code:\n{repaired['patch_code']}")

    asyncio.run(_test())
