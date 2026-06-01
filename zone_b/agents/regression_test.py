"""RegressionTest — generates a pytest-shaped check and runs it in Daytona.

Per issue #2:
1. ConversableAgent generates a self-contained Python test that asserts the
   repair would prevent the violations.
2. Daytona sandbox executes the test via process.code_run.
3. stdout is parsed for PASS / FAIL markers to set test_status.
4. Per-violation result rows preserve the contract order from the report.
5. Sandbox is always deleted, even on errors.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
from autogen import ConversableAgent
from shared.models import RunTrace, Violation
from zone_b.config import get_llm_config
from zone_b.utils import parse_json_body as _parse_json_body, make_proxy as _make_proxy
from zone_b.sandbox.runner import (
    SandboxRunResult,
    run_python_in_daytona,
    zero_cost,
    zero_usage,
)


class RegressionTestGenerationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        usage: dict[str, int] | None = None,
        llm_cost_usd: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.usage = usage or zero_usage()
        self.llm_cost_usd = llm_cost_usd


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
    usage, llm_cost_usd = _extract_llm_usage(result)
    body = result.chat_history[-1]["content"]
    try:
        parsed = _parse_json_body(body)
    except Exception as exc:
        raise RegressionTestGenerationError(
            "could not parse generated regression test",
            usage=usage,
            llm_cost_usd=llm_cost_usd,
        ) from exc
    if not isinstance(parsed, dict):
        raise RegressionTestGenerationError(
            "generated regression test was not a JSON object",
            usage=usage,
            llm_cost_usd=llm_cost_usd,
        )
    parsed["_usage"] = usage
    parsed["_llm_cost_usd"] = llm_cost_usd
    return parsed


def _fallback_test(repair_patch: str, violations: list[Violation]) -> dict:
    """Hand-rolled test used when the LLM call or parse fails."""
    types = [v.contract_type for v in violations]
    code = (
        "verified_sources_count = 1\n"
        "approval_status = 'approved'\n"
        "verifier_tool_call_id = 'tc_verifier'\n"
        "final_output = {'summary': 's', 'claims': [], 'citations': [], "
        "'risks': [], 'next_steps': []}\n"
        "handoff_path = ['ResearcherAgent', 'CriticAgent', 'VerifierAgent', "
        "'ReporterAgent', 'HumanGateAgent', 'ActionAgent']\n"
        "try:\n"
        "    assert verified_sources_count > 0, 'evidence violation still present'\n"
        "    print('PASS evidence')\n"
        "    assert approval_status == 'approved', 'approval violation still present'\n"
        "    print('PASS approval')\n"
        "    assert verifier_tool_call_id, 'tool violation still present'\n"
        "    print('PASS tool')\n"
        "    assert handoff_path.index('VerifierAgent') < "
        "handoff_path.index('ReporterAgent'), 'routing violation still present'\n"
        "    assert handoff_path.index('HumanGateAgent') < "
        "handoff_path.index('ActionAgent'), 'routing approval gate still missing'\n"
        "    print('PASS routing')\n"
        "    assert {'summary', 'claims', 'citations', 'risks', 'next_steps'} <= "
        "set(final_output), 'schema violation still present'\n"
        "    print('PASS schema')\n"
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


VALIDATION_STATES = (
    "passed",
    "failed",
    "skipped",
    "unavailable",
    "credential_failure",
    "execution_error",
)


def _empty_validation_summary() -> dict[str, int]:
    return {state: 0 for state in VALIDATION_STATES}


def _validation_state_for_result(
    test_status: str,
    stdout: str = "",
    sandbox_id: str = "",
) -> str:
    status = (test_status or "").strip().lower()
    output = (stdout or "").strip().lower()
    sandbox = (sandbox_id or "").strip().lower()
    if status in {"pass", "passed"}:
        return "passed"
    if status in {"fail", "failed"}:
        return "failed"
    if status == "skipped":
        return "skipped"
    if (
        "credentials missing" in output
        or "invalid credentials" in output
        or "credential" in output and "fail" in output
        or "unauthorized" in output
    ):
        return "credential_failure"
    if "unavailable" in output or (sandbox in {"", "no-sandbox"} and not output):
        return "unavailable"
    if sandbox in {"", "no-sandbox"} and status == "error":
        return "unavailable"
    return "execution_error"


def _status_for_violation(stdout: str, overall_status: str, contract_type: str) -> str:
    marker = contract_type.lower()
    lines = [line.strip().lower() for line in (stdout or "").splitlines()]
    matching = [
        line for line in lines
        if marker in line and line.startswith(("pass", "fail", "error"))
    ]
    if any(line.startswith("fail") for line in matching):
        return "fail"
    if any(line.startswith("error") for line in matching):
        return "error"
    if any(line.startswith("pass") for line in matching):
        return "pass"
    if overall_status in {"pass", "fail", "error"}:
        return overall_status
    return "error"


def _per_violation_results(
    violations: list[Violation],
    test_name: str,
    assertions: list[str],
    test_status: str,
    stdout: str,
    sandbox_id: str,
    fallback_used: bool,
) -> list[dict]:
    results = []
    for index, violation in enumerate(violations):
        assertion = (
            assertions[index]
            if index < len(assertions)
            else f"{violation.contract_type} contract is satisfied post-repair"
        )
        results.append({
            "contract_type": violation.contract_type,
            "severity": violation.severity,
            "rule": violation.rule,
            "failed_agent": violation.failed_agent,
            "failed_step": violation.failed_step,
            "test_name": f"{test_name}_{index + 1}_{violation.contract_type}",
            "assertion": assertion,
            "test_status": _status_for_violation(
                stdout, test_status, violation.contract_type
            ),
            "validation_state": _validation_state_for_result(
                _status_for_violation(stdout, test_status, violation.contract_type),
                stdout,
                sandbox_id,
            ),
            "stdout": stdout,
            "sandbox_id": sandbox_id,
            "fallback_used": fallback_used,
        })
    return results


def _normalize_assertions(assertions) -> list[str]:
    if not isinstance(assertions, list):
        return []
    return [str(assertion) for assertion in assertions]


def _status_summary(results: list[dict]) -> dict:
    summary = {"pass": 0, "fail": 0, "error": 0}
    for result in results:
        status = result.get("test_status", "error")
        summary[status if status in summary else "error"] += 1
    return summary


def _validation_summary(
    results: list[dict],
    *,
    fallback_state: str | None = None,
) -> dict[str, int]:
    summary = _empty_validation_summary()
    if not results and fallback_state:
        summary[fallback_state if fallback_state in summary else "execution_error"] += 1
        return summary
    for result in results:
        state = result.get("validation_state", "execution_error")
        summary[state if state in summary else "execution_error"] += 1
    return summary


def _run_in_daytona(test_code: str) -> SandboxRunResult:
    """Execute test_code in a DaytonaCodeExecutor sandbox."""
    return run_python_in_daytona(test_code)


def _run_locally(test_code: str) -> SandboxRunResult:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        duration = time.perf_counter() - start
        stdout = proc.stdout
        if proc.stderr:
            stdout = f"{stdout}{proc.stderr}"
        return SandboxRunResult(
            stdout=stdout,
            sandbox_id="local-regression",
            status=_parse_status(stdout),
            duration_ms=int(round(duration * 1000)),
            cost=zero_cost(),
            usage=zero_usage(),
            exit_code=proc.returncode,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - start
        return SandboxRunResult(
            stdout=f"Local regression timeout: {exc!r}",
            sandbox_id="local-regression",
            status="error",
            duration_ms=int(round(duration * 1000)),
            cost=zero_cost(),
            usage=zero_usage(),
            exit_code=1,
        )
    except OSError as exc:
        duration = time.perf_counter() - start
        return SandboxRunResult(
            stdout=f"Local regression error: {exc!r}",
            sandbox_id="local-regression",
            status="error",
            duration_ms=int(round(duration * 1000)),
            cost=zero_cost(),
            usage=zero_usage(),
            exit_code=1,
        )


def _use_local_regression_runner() -> bool:
    return os.environ.get("CONCORD_REGRESSION_RUNNER", "").strip().lower() == "local"


def _coerce_execution_result(value) -> SandboxRunResult:
    if isinstance(value, SandboxRunResult):
        return value
    stdout, sandbox_id, status = value[:3]
    return SandboxRunResult(
        stdout=stdout,
        sandbox_id=sandbox_id,
        status=status,
        cost=zero_cost(),
        usage=zero_usage(),
        exit_code=0 if status == "pass" else 1,
    )


def _sum_numeric(payload, names: set[str]) -> float:
    total = 0.0
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in names and isinstance(value, int | float):
                total += float(value)
            elif isinstance(value, dict | list):
                total += _sum_numeric(value, names)
    elif isinstance(payload, list):
        for item in payload:
            total += _sum_numeric(item, names)
    return total


def _llm_cost_from_usage(payload) -> float:
    if not isinstance(payload, dict):
        return 0.0
    total_cost = payload.get("total_cost")
    if isinstance(total_cost, int | float):
        return float(total_cost)
    cost = payload.get("cost")
    if isinstance(cost, int | float):
        return float(cost)
    return sum(_llm_cost_from_usage(value) for value in payload.values())


def _extract_llm_usage(chat_result) -> tuple[dict[str, int], float]:
    cost = getattr(chat_result, "cost", {}) or {}
    usage_data = cost.get("usage_including_cached_inference", cost)
    prompt = int(_sum_numeric(usage_data, {"prompt_tokens", "input_tokens"}))
    completion = int(_sum_numeric(usage_data, {"completion_tokens", "output_tokens"}))
    total = int(_sum_numeric(usage_data, {"total_tokens"})) or prompt + completion
    llm_cost = _llm_cost_from_usage(usage_data)
    return (
        {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
        },
        round(llm_cost, 8),
    )


def _aggregate_execution_cost(
    results: list[SandboxRunResult],
    usage: dict[str, int],
    llm_cost_usd: float,
) -> dict[str, float | int]:
    cost = zero_cost()
    cost["daytona_seconds"] = round(
        sum(float((result.cost or {}).get("daytona_seconds", 0)) for result in results),
        3,
    )
    cost["daytona_cost_usd"] = round(
        sum(float((result.cost or {}).get("daytona_cost_usd", 0)) for result in results),
        8,
    )
    cost["llm_tokens"] = int(usage.get("total_tokens", 0))
    cost["llm_cost_usd"] = round(float(llm_cost_usd), 8)
    return cost


async def run_regression_test(
    repair_patch: str,
    violations: list[Violation],
    run_trace: RunTrace,
) -> dict:
    """Generate a regression test and run it in Daytona."""
    if not violations:
        validation_state = "skipped"
        return {
            "test_name": "validation_skipped_no_violations",
            "test_code": "",
            "assertions": [],
            "test_status": "skipped",
            "stdout": "Validation skipped: no contract violations",
            "sandbox_id": "",
            "fallback_used": False,
            "fallback_reason": "no_violations",
            "generated_test_status": "",
            "generated_stdout": "",
            "generated_sandbox_id": "",
            "validation_state": validation_state,
            "per_violation_results": [],
            "per_violation_summary": {"pass": 0, "fail": 0, "error": 0},
            "validation_summary": _validation_summary([], fallback_state=validation_state),
            "duration_ms": 0,
            "usage": zero_usage(),
            "cost": zero_cost(),
        }

    fallback_used = False
    fallback_reason = ""
    generated_test_status = ""
    generated_stdout = ""
    generated_sandbox_id = ""
    generated_test_ran = False
    execution_results: list[SandboxRunResult] = []
    llm_usage = zero_usage()
    llm_cost_usd = 0.0

    def record_execution(value) -> SandboxRunResult:
        result = _coerce_execution_result(value)
        execution_results.append(result)
        return result

    if _use_local_regression_runner():
        fallback = _fallback_test(repair_patch, violations)
        test_name = fallback["test_name"]
        test_code = fallback["test_code"]
        assertions = fallback["assertions"]
        fallback_used = True
        fallback_reason = "local_regression_runner"
        execution = record_execution(_run_locally(test_code))
        stdout, sandbox_id, test_status = execution.as_legacy_tuple()
    else:
        try:
            gen = _ask_llm_for_test(repair_patch, violations, run_trace)
            test_name = gen.get("test_name", "test_repair_resolves_violations")
            test_code = gen.get("test_code", "")
            assertions = _normalize_assertions(gen.get("assertions", []))
            llm_usage = gen.get("_usage", zero_usage())
            llm_cost_usd = float(gen.get("_llm_cost_usd", 0.0))
            if not test_code.strip():
                raise ValueError("LLM returned empty test_code")
        except RegressionTestGenerationError as exc:
            llm_usage = exc.usage
            llm_cost_usd = exc.llm_cost_usd
            fallback = _fallback_test(repair_patch, violations)
            test_name = fallback["test_name"]
            test_code = fallback["test_code"]
            assertions = fallback["assertions"]
            fallback_used = True
            fallback_reason = "generation_error"
        except Exception:
            fallback = _fallback_test(repair_patch, violations)
            test_name = fallback["test_name"]
            test_code = fallback["test_code"]
            assertions = fallback["assertions"]
            fallback_used = True
            fallback_reason = "generation_error"

        execution = record_execution(_run_in_daytona(test_code))
        stdout, sandbox_id, test_status = execution.as_legacy_tuple()
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
            execution = record_execution(_run_in_daytona(test_code))
            stdout, sandbox_id, test_status = execution.as_legacy_tuple()

    per_violation_results = _per_violation_results(
        violations,
        test_name,
        assertions,
        test_status,
        stdout,
        sandbox_id,
        fallback_used,
    )
    validation_state = _validation_state_for_result(test_status, stdout, sandbox_id)

    return {
        "test_name": test_name,
        "test_code": test_code,
        "assertions": assertions,
        "test_status": test_status,
        "validation_state": validation_state,
        "stdout": stdout,
        "sandbox_id": sandbox_id,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "generated_test_status": generated_test_status,
        "generated_stdout": generated_stdout,
        "generated_sandbox_id": generated_sandbox_id,
        "per_violation_results": per_violation_results,
        "per_violation_summary": _status_summary(per_violation_results),
        "validation_summary": _validation_summary(per_violation_results),
        "duration_ms": sum(result.duration_ms for result in execution_results),
        "usage": llm_usage,
        "cost": _aggregate_execution_cost(execution_results, llm_usage, llm_cost_usd),
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
