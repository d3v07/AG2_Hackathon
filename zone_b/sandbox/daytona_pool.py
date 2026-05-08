"""Warm DaytonaCodeExecutor pool for regression execution."""
from __future__ import annotations

import os
from collections.abc import Callable
from queue import Empty, LifoQueue
from threading import Lock
from typing import Any

from autogen.coding import DaytonaCodeExecutor

from zone_b.sandbox.runner import SandboxRunResult, execute_python_with_executor


class DaytonaExecutorPool:
    def __init__(
        self,
        *,
        size: int = 1,
        timeout: int = 60,
        executor_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.size = max(1, int(size))
        self.timeout = max(1, int(timeout))
        self.acquire_timeout = float(os.environ.get("CONCORD_DAYTONA_ACQUIRE_TIMEOUT", "30"))
        self._executor_factory = executor_factory or self._default_executor_factory
        self._available: LifoQueue[Any] = LifoQueue(maxsize=self.size)
        self._executors: list[Any] = []
        self._lock = Lock()
        self._closed = False
        self.warm()

    @classmethod
    def from_environment(cls) -> "DaytonaExecutorPool":
        size = int(os.environ.get("CONCORD_DAYTONA_POOL_SIZE", "1"))
        timeout = int(os.environ.get("CONCORD_DAYTONA_TIMEOUT", "60"))
        return cls(size=size, timeout=timeout)

    def __enter__(self) -> "DaytonaExecutorPool":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _default_executor_factory(self) -> DaytonaCodeExecutor:
        image = os.environ.get("CONCORD_DAYTONA_IMAGE") or None
        snapshot = os.environ.get("CONCORD_DAYTONA_SNAPSHOT") or None
        kwargs: dict[str, Any] = {
            "api_key": os.environ.get("DAYTONA_API_KEY") or None,
            "api_url": os.environ.get("DAYTONA_API_URL") or None,
            "target": os.environ.get("DAYTONA_TARGET") or None,
            "timeout": self.timeout,
        }
        if image:
            kwargs["image"] = image
        elif snapshot:
            kwargs["snapshot"] = snapshot
        return DaytonaCodeExecutor(**kwargs)

    def warm(self) -> None:
        self._ensure_open()
        with self._lock:
            while len(self._executors) < self.size:
                executor = self._executor_factory()
                self._executors.append(executor)
                self._available.put(executor)

    def acquire(self) -> Any:
        self._ensure_open()
        try:
            return self._available.get(timeout=self.acquire_timeout)
        except Empty as exc:
            raise RuntimeError("No Daytona executor is available in the pool") from exc

    def release(self, executor: Any) -> None:
        self._ensure_open()
        if executor in self._executors:
            reset = getattr(executor, "restart", None)
            if callable(reset):
                try:
                    reset()
                except Exception:
                    self._replace_executor(executor)
                    return
            self._available.put(executor)

    def run_python(self, code: str) -> SandboxRunResult:
        executor = self.acquire()
        try:
            return execute_python_with_executor(executor, code)
        finally:
            self.release(executor)

    def _replace_executor(self, executor: Any) -> None:
        with self._lock:
            if executor in self._executors:
                self._executors.remove(executor)
            delete = getattr(executor, "delete", None)
            if callable(delete):
                try:
                    delete()
                except Exception:
                    pass
            replacement = self._executor_factory()
            self._executors.append(replacement)
            self._available.put(replacement)

    def close(self) -> None:
        if self._closed:
            return
        for executor in list(self._executors):
            delete = getattr(executor, "delete", None)
            if callable(delete):
                try:
                    delete()
                except Exception:
                    pass
        while not self._available.empty():
            try:
                self._available.get_nowait()
            except Empty:
                break
        self._executors.clear()
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Daytona executor pool is closed")
