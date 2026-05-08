"""Executable contract types for Zone B."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from shared.models import ContextSnapshot, RunTrace

ContractCheck = Callable[[RunTrace, ContextSnapshot], bool]


@dataclass(frozen=True)
class Contract:
    id: str
    type: str
    severity: str
    rule_text: str
    failed_agent: str
    check_callable: ContractCheck
    dsl: dict[str, Any] = field(default_factory=dict)

    @property
    def rule(self) -> str:
        return self.rule_text

    @property
    def check(self) -> ContractCheck:
        return self.check_callable

    def __getitem__(self, key: str):
        values = {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "rule": self.rule_text,
            "failed_agent": self.failed_agent,
            "check": self.check_callable,
        }
        return values[key]

    def __contains__(self, key: object) -> bool:
        return key in {"id", "type", "severity", "rule", "failed_agent", "check"}

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self) -> tuple[str, ...]:
        return ("id", "type", "severity", "rule", "failed_agent", "check")

    def to_dict(self) -> dict[str, str]:
        data = {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "rule": self.rule_text,
            "failed_agent": self.failed_agent,
        }
        data.update(self.dsl)
        return data
