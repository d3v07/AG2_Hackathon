"""Process-local run event bus for dashboard streams."""
from __future__ import annotations

import secrets
import time
from queue import Empty, Queue
from threading import RLock
from typing import Any

TERMINAL_STATUSES = {"completed", "failed"}


def run_event_payload(
    *,
    run_id: str,
    workflow_id: str,
    status: str,
    status_history: list[str],
    error: str = "",
) -> dict[str, Any]:
    sequence = len(status_history) if status_history else 1
    return {
        "type": "run.status",
        "run_id": run_id,
        "workflow_id": workflow_id,
        "status": status,
        "error": error,
        "status_history": list(status_history),
        "sequence": sequence,
        "terminal": status in TERMINAL_STATUSES,
    }


def replay_status_events(status: dict[str, Any]) -> list[dict[str, Any]]:
    history = status.get("status_history") or [status.get("status", "")]
    events: list[dict[str, Any]] = []
    for index, status_value in enumerate(history, start=1):
        history_slice = list(history[:index])
        error = status.get("error", "") if status_value == status.get("status") else ""
        events.append(
            run_event_payload(
                run_id=status["run_id"],
                workflow_id=status.get("workflow_id", ""),
                status=status_value,
                status_history=history_slice,
                error=error,
            )
        )
    return events


class RunEventSubscription:
    def __init__(self, bus: "RunEventBus", tenant_id: str, run_id: str) -> None:
        self._bus = bus
        self._tenant_id = tenant_id
        self._run_id = run_id
        self._queue: Queue[dict[str, Any] | None] = Queue()
        self._closed = False

    def put(self, event: dict[str, Any]) -> None:
        if not self._closed:
            self._queue.put(event)

    def get(self, timeout: float | None = None) -> dict[str, Any] | None:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def get_nowait(self) -> dict[str, Any] | None:
        return self.get(timeout=0)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._bus.unsubscribe(self._tenant_id, self._run_id, self)
        self._queue.put(None)


class RunEventBus:
    def __init__(self) -> None:
        self._lock = RLock()
        self._subscribers: dict[tuple[str, str], set[RunEventSubscription]] = {}

    def subscribe(self, tenant_id: str, run_id: str) -> RunEventSubscription:
        subscription = RunEventSubscription(self, tenant_id, run_id)
        key = (tenant_id, run_id)
        with self._lock:
            self._subscribers.setdefault(key, set()).add(subscription)
        return subscription

    def unsubscribe(
        self,
        tenant_id: str,
        run_id: str,
        subscription: RunEventSubscription,
    ) -> None:
        key = (tenant_id, run_id)
        with self._lock:
            subscribers = self._subscribers.get(key)
            if not subscribers:
                return
            subscribers.discard(subscription)
            if not subscribers:
                self._subscribers.pop(key, None)

    def publish(self, tenant_id: str, run_id: str, event: dict[str, Any]) -> None:
        key = (tenant_id, run_id)
        with self._lock:
            subscribers = list(self._subscribers.get(key, ()))
        for subscription in subscribers:
            subscription.put(dict(event))

    def subscriber_count(self, tenant_id: str, run_id: str) -> int:
        with self._lock:
            return len(self._subscribers.get((tenant_id, run_id), ()))


run_event_bus = RunEventBus()


def publish_run_event(tenant_id: str, event: dict[str, Any]) -> None:
    run_event_bus.publish(tenant_id, event["run_id"], event)


class RunEventTokenStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._tokens: dict[str, dict[str, Any]] = {}

    def create(self, tenant_id: str, run_id: str, ttl_seconds: int = 300) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = time.time() + ttl_seconds
        with self._lock:
            self._purge_expired_locked()
            self._tokens[token] = {
                "tenant_id": tenant_id,
                "run_id": run_id,
                "expires_at": expires_at,
            }
        return token

    def validate(self, token: str, run_id: str) -> str | None:
        with self._lock:
            payload = self._tokens.get(token)
            if not payload:
                return None
            if payload["expires_at"] <= time.time():
                self._tokens.pop(token, None)
                return None
            if payload["run_id"] != run_id:
                return None
            return str(payload["tenant_id"])

    def _purge_expired_locked(self) -> None:
        now = time.time()
        expired = [
            token for token, payload in self._tokens.items()
            if payload["expires_at"] <= now
        ]
        for token in expired:
            self._tokens.pop(token, None)


run_event_tokens = RunEventTokenStore()
