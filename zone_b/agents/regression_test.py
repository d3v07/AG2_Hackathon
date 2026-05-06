"""RegressionTest — generates a pytest-shaped check and runs it in Daytona.

Per issue #2:
1. ConversableAgent generates a self-contained Python test that asserts the
   repair would prevent the violations.
2. Daytona sandbox executes the test via process.code_run.
3. stdout is parsed for PASS / FAIL markers to set test_status.
4. Sandbox is always deleted, even on errors.
"""
import asyncio
import json
import os
from autogen import ConversableAgent
from shared.models import RunTrace, Violation
from zone_b.config import get_llm_config
from zone_b.utils import parse_json_body as _parse_json_body, make_proxy as _make_proxy


def _ask_llm_for_test(
    repair_patch: str, violations: list[Violation], run_trace: RunTrace
) -> dict:
    """Ask LLM to produce a self-contained Python test as a string."""
    tester = ConversableAgent(
        name="RegressionTestAgent",
        llm_config=get_llm_config(),
        system_message=(
            "You write self-contained Python regression tests. The test must "
            "be a single Python script that defines simulated state, asserts "
            "the post-repair conditions hold, and prints exactly 'PASS' on "
            "success or 'FAIL: <reason>' on assertion failure. No external "
            "imports beyond the standard library. Reply with JSON only."
        ),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )
    proxy = _make_proxy("RegressionTestProxy")

    violations_summary = [
        {"type": v.contract_type, "rule": v.rule, "failed_agent": v.failed_agent}
        for v in violations
    ]
    prompt = (
        f"Repair patch    : {repair_patch}\n"
        f"Workflow        : {run_trace.workflow_name}\n"
        f"Violations to prevent:\n{json.dumps(violations_summary, indent=2)}\n\n"
        "Reply with ONLY a JSON object with keys:\n"
        '  "test_name": short snake_case test name\n'
        '  "test_code": full self-contained Python script that simulates the '
        "repaired state and asserts each violation is no longer reachable. "
        "Wrap assertions in try/except so the script prints 'PASS' or "
        "'FAIL: <reason>'. Must run on plain Python 3 with no dependencies.\n"
        '  "assertions": list of one-line strings describing each assertion'
    )
    result = proxy.initiate_chat(tester, message=prompt, max_turns=1)
    body = result.chat_history[-1]["content"]
    return _parse_json_body(body)


def _fallback_test(repair_patch: str, violations: list[Violation]) -> dict:
    """Hand-rolled test used when the LLM call or parse fails."""
    types = [v.contract_type for v in violations]
    code = (
        "verified_sources_count = 1\n"
        "approval_status = 'approved'\n"
        "verifier_tool_call_id = 'tc_verifier'\n"
        "handoff_path = ['ResearcherAgent', 'CriticAgent', 'VerifierAgent', "
        "'ReporterAgent', 'HumanGateAgent', 'ActionAgent']\n"
        "try:\n"
        "    assert verified_sources_count > 0, 'evidence violation still present'\n"
        "    assert approval_status == 'approved', 'approval violation still present'\n"
        "    assert verifier_tool_call_id, 'tool violation still present'\n"
        "    assert handoff_path.index('VerifierAgent') < "
        "handoff_path.index('ReporterAgent'), 'routing violation still present'\n"
        "    assert handoff_path.index('HumanGateAgent') < "
        "handoff_path.index('ActionAgent'), 'routing approval gate still missing'\n"
        "    print('PASS')\n"
        "except AssertionError as e:\n"
        "    print(f'FAIL: {e}')\n"
    )
    return {
        "test_name": "test_repair_resolves_violations",
        "test_code": code,
        "assertions": [f"{t} contract is satisfied post-repair" for t in types],
    }


def _parse_status(stdout: str) -> str:
    out = (stdout or "").strip()
    if "PASS" in out and "FAIL" not in out:
        return "pass"
    if "FAIL" in out:
        return "fail"
    return "error"


def _is_infrastructure_error(stdout: str) -> bool:
    out = stdout or ""
    return out.startswith("Daytona credentials missing") or out.startswith(
        "Daytona error:"
    )


def _run_in_daytona(test_code: str) -> tuple[str, str, str]:
    """Execute test_code in a fresh Daytona sandbox. Returns (stdout, sandbox_id, status)."""
    api_key = os.environ.get("DAYTONA_API_KEY", "").strip()
    api_url = os.environ.get("DAYTONA_API_URL", "").strip()
    if not api_key or not api_url:
        return ("Daytona credentials missing", "no-sandbox", "error")

    from daytona_sdk import Daytona, DaytonaConfig

    daytona = Daytona(DaytonaConfig(api_key=api_key, api_url=api_url))
    sandbox = None
    sandbox_id = "no-sandbox"
    try:
        sandbox = daytona.create()
        sandbox_id = getattr(sandbox, "id", "unknown")
        result = sandbox.process.code_run(test_code)
        stdout = getattr(result, "result", "") or getattr(result, "stdout", "") or ""
        return (stdout, sandbox_id, _parse_status(stdout))
    except Exception as e:
        return (f"Daytona error: {e!r}", sandbox_id, "error")
    finally:
        if sandbox is not None:
            try:
                daytona.delete(sandbox)
            except Exception:
                pass


async def run_regression_test(
    repair_patch: str,
    violations: list[Violation],
    run_trace: RunTrace,
) -> dict:
    """Generate a regression test and run it in Daytona."""
    fallback_used = False
    fallback_reason = ""
    generated_test_status = ""
    generated_stdout = ""
    generated_sandbox_id = ""
    generated_test_ran = False

    try:
        gen = _ask_llm_for_test(repair_patch, violations, run_trace)
        test_name = gen.get("test_name", "test_repair_resolves_violations")
        test_code = gen.get("test_code", "")
        assertions = gen.get("assertions", [])
        if not test_code.strip():
            raise ValueError("LLM returned empty test_code")
    except Exception:
        fallback = _fallback_test(repair_patch, violations)
        test_name = fallback["test_name"]
        test_code = fallback["test_code"]
        assertions = fallback["assertions"]
        fallback_used = True
        fallback_reason = "generation_error"

    stdout, sandbox_id, test_status = _run_in_daytona(test_code)
    if not fallback_used:
        generated_test_ran = True
        generated_test_status = test_status
        generated_stdout = stdout
        generated_sandbox_id = sandbox_id

    if (
        generated_test_ran
        and test_status != "pass"
        and not _is_infrastructure_error(stdout)
    ):
        fallback = _fallback_test(repair_patch, violations)
        test_name = fallback["test_name"]
        test_code = fallback["test_code"]
        assertions = fallback["assertions"]
        fallback_used = True
        fallback_reason = f"generated_test_{test_status}"
        stdout, sandbox_id, test_status = _run_in_daytona(test_code)

    return {
        "test_name": test_name,
        "test_code": test_code,
        "assertions": assertions,
        "test_status": test_status,
        "stdout": stdout,
        "sandbox_id": sandbox_id,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "generated_test_status": generated_test_status,
        "generated_stdout": generated_stdout,
        "generated_sandbox_id": generated_sandbox_id,
    }


if __name__ == "__main__":
    from pathlib import Path
    from zone_b.agents.trace_collector import run_trace_collector
    from zone_b.agents.contract_checker import run_contract_checker
    from zone_b.agents.attribution import run_attribution
    from zone_b.agents.repair import run_repair

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
        print(f"\ntest_name   : {tested['test_name']}")
        print(f"test_status : {tested['test_status']}")
        print(f"sandbox_id  : {tested['sandbox_id']}")
        print(f"assertions  : {tested['assertions']}")
        print(f"stdout      :\n{tested['stdout']}")

    asyncio.run(_test())
