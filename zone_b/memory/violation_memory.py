"""Stable recurrence identity for contract violations."""
from __future__ import annotations

from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def contract_type(violation: dict[str, Any]) -> str:
    raw = violation.get("contract_type") or violation.get("type") or violation.get("contract")
    value = _clean(raw).lower()
    if value.startswith("c-"):
        return value
    return value


def rule(violation: dict[str, Any]) -> str:
    return _clean(violation.get("rule") or violation.get("title") or violation.get("expected"))


def failed_agent(violation: dict[str, Any]) -> str:
    return _clean(violation.get("failed_agent") or violation.get("agent"))


def recurrence_key(violation: dict[str, Any]) -> str:
    """Return a stable workflow-scoped identity for recurring violations."""
    return "|".join(
        [
            contract_type(violation),
            failed_agent(violation),
            rule(violation),
        ]
    )
