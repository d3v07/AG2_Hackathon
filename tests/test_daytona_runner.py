"""DaytonaCodeExecutor runner boundary tests."""
from __future__ import annotations

from zone_b.sandbox.runner import SandboxRunResult, run_python_in_daytona
from zone_b.sandbox.daytona_pool import DaytonaExecutorPool


class _FakeCodeResult:
    def __init__(self, output: str, sandbox_id: str = "sb-warm", exit_code: int = 0):
        self.output = output
        self.sandbox_id = sandbox_id
        self.exit_code = exit_code


class _FakeExecutor:
    def __init__(self, sandbox_id: str = "sb-warm"):
        self.sandbox_id = sandbox_id
        self.deleted = False
        self.restarts = 0
        self.calls: list[str] = []

    def execute_code_blocks(self, code_blocks):
        self.calls.append(code_blocks[0].code)
        return _FakeCodeResult("PASS", self.sandbox_id)

    def restart(self):
        self.restarts += 1

    def delete(self):
        self.deleted = True


def test_pool_reuses_warm_executor_and_deletes_on_close():
    created: list[_FakeExecutor] = []

    def factory():
        executor = _FakeExecutor()
        created.append(executor)
        return executor

    pool = DaytonaExecutorPool(size=1, executor_factory=factory)

    first = pool.run_python("print('PASS one')")
    second = pool.run_python("print('PASS two')")
    pool.close()

    assert len(created) == 1
    assert first.sandbox_id == "sb-warm"
    assert second.sandbox_id == "sb-warm"
    assert created[0].calls == ["print('PASS one')", "print('PASS two')"]
    assert created[0].restarts == 2
    assert created[0].deleted is True


def test_pool_resets_executor_state_between_runs():
    class StatefulExecutor(_FakeExecutor):
        def __init__(self):
            super().__init__()
            self.state = set()

        def execute_code_blocks(self, code_blocks):
            code = code_blocks[0].code
            if code == "write_state":
                self.state.add("dirty")
                return _FakeCodeResult("PASS", self.sandbox_id)
            if code == "assert_clean":
                output = "FAIL: leaked state" if self.state else "PASS"
                return _FakeCodeResult(output, self.sandbox_id)
            return _FakeCodeResult("PASS", self.sandbox_id)

        def restart(self):
            super().restart()
            self.state.clear()

    pool = DaytonaExecutorPool(size=1, executor_factory=StatefulExecutor)

    first = pool.run_python("write_state")
    second = pool.run_python("assert_clean")
    pool.close()

    assert first.status == "pass"
    assert second.status == "pass"


def test_missing_daytona_credentials_return_explicit_error(monkeypatch):
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    monkeypatch.delenv("DAYTONA_API_URL", raising=False)

    result = run_python_in_daytona("print('PASS')")

    assert isinstance(result, SandboxRunResult)
    assert result.status == "error"
    assert result.sandbox_id == "no-sandbox"
    assert result.stdout == "Daytona credentials missing"
    assert result.cost["daytona_seconds"] == 0
    assert result.cost["daytona_cost_usd"] == 0


def test_daytona_result_records_duration_and_nonzero_cost(monkeypatch):
    monkeypatch.setenv("DAYTONA_API_KEY", "key")
    monkeypatch.setenv("DAYTONA_API_URL", "https://daytona.example.test")
    ticks = iter([10.0, 11.25])
    monkeypatch.setattr("zone_b.sandbox.runner.time.perf_counter", lambda: next(ticks))

    pool = DaytonaExecutorPool(size=1, executor_factory=lambda: _FakeExecutor())
    result = run_python_in_daytona("print('PASS')", pool=pool)

    assert result.status == "pass"
    assert result.duration_ms == 1250
    assert result.cost["daytona_seconds"] == 1.25
    assert result.cost["daytona_cost_usd"] > 0
    assert result.cost["llm_tokens"] == 0
    pool.close()
