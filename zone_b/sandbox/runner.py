"""Daytona sandbox runner built on AG2's DaytonaCodeExecutor."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from autogen.coding.base import CodeBlock

DEFAULT_DAYTONA_COST_PER_SECOND_USD = 0.0002

_daytona_pool = None


@dataclass(frozen=True)
class SandboxRunResult:
    stdout: str
    sandbox_id: str
    status: str
    duration_ms: int = 0
    cost: dict[str, float | int] | None = None
    usage: dict[str, int] | None = None
    exit_code: int = 0

    def as_legacy_tuple(self) -> tuple[str, str, str]:
        return self.stdout, self.sandbox_id, self.status


def zero_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def zero_cost() -> dict[str, float | int]:
    return {
        "daytona_seconds": 0,
        "llm_tokens": 0,
        "llm_cost_usd": 0,
        "daytona_cost_usd": 0,
    }


def _daytona_rate() -> float:
    raw = os.environ.get("CONCORD_DAYTONA_COST_PER_SECOND_USD", "")
    if not raw:
        return DEFAULT_DAYTONA_COST_PER_SECOND_USD
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_DAYTONA_COST_PER_SECOND_USD


def _cost_for_duration(duration_seconds: float) -> dict[str, float | int]:
    seconds = round(max(0.0, duration_seconds), 3)
    cost = zero_cost()
    cost["daytona_seconds"] = seconds
    cost["daytona_cost_usd"] = round(seconds * _daytona_rate(), 8)
    return cost


def _status_from_output(output: str, exit_code: int) -> str:
    text = (output or "").strip()
    if "PASS" in text and "FAIL" not in text and exit_code == 0:
        return "pass"
    if "FAIL" in text:
        return "fail"
    return "error"


def _sandbox_id_from_executor(executor: Any, result: Any | None = None) -> str:
    if result is not None and getattr(result, "sandbox_id", None):
        return result.sandbox_id
    if getattr(executor, "sandbox_id", None):
        return executor.sandbox_id
    sandbox = getattr(executor, "_sandbox", None)
    if getattr(sandbox, "id", None):
        return sandbox.id
    return "unknown"


def execution_error(stdout: str, *, duration_seconds: float = 0.0, sandbox_id: str = "no-sandbox") -> SandboxRunResult:
    return SandboxRunResult(
        stdout=stdout,
        sandbox_id=sandbox_id,
        status="error",
        duration_ms=int(round(max(0.0, duration_seconds) * 1000)),
        cost=_cost_for_duration(0.0 if sandbox_id == "no-sandbox" else duration_seconds),
        usage=zero_usage(),
        exit_code=1,
    )


def execute_python_with_executor(executor: Any, code: str) -> SandboxRunResult:
    start = time.perf_counter()
    try:
        result = executor.execute_code_blocks([CodeBlock(code=code, language="python")])
        duration = time.perf_counter() - start
        stdout = getattr(result, "output", "") or ""
        exit_code = int(getattr(result, "exit_code", 1))
        return SandboxRunResult(
            stdout=stdout,
            sandbox_id=_sandbox_id_from_executor(executor, result),
            status=_status_from_output(stdout, exit_code),
            duration_ms=int(round(duration * 1000)),
            cost=_cost_for_duration(duration),
            usage=zero_usage(),
            exit_code=exit_code,
        )
    except Exception as exc:
        duration = time.perf_counter() - start
        return execution_error(
            f"Daytona error: {exc!r}",
            duration_seconds=duration,
            sandbox_id=_sandbox_id_from_executor(executor),
        )


def _credentials_present() -> bool:
    return bool(os.environ.get("DAYTONA_API_KEY", "").strip()) and bool(
        os.environ.get("DAYTONA_API_URL", "").strip()
    )


def get_daytona_pool():
    global _daytona_pool
    if _daytona_pool is None:
        from zone_b.sandbox.daytona_pool import DaytonaExecutorPool

        _daytona_pool = DaytonaExecutorPool.from_environment()
    return _daytona_pool


def close_daytona_pool() -> None:
    global _daytona_pool
    if _daytona_pool is not None:
        _daytona_pool.close()
        _daytona_pool = None


def run_python_in_daytona(code: str, *, pool=None) -> SandboxRunResult:
    if not _credentials_present():
        return execution_error("Daytona credentials missing")
    try:
        active_pool = pool if pool is not None else get_daytona_pool()
        return active_pool.run_python(code)
    except Exception as exc:
        return execution_error(f"Daytona error: {exc!r}")
