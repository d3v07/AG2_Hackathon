from dataclasses import dataclass, field
from typing import Any


@dataclass
class ZoneAContext:
    retrieved_sources: list = field(default_factory=list)
    tool_events: list = field(default_factory=list)
    # Intentionally stays 0 — VerifierAgent is broken by design (Contract C1 violation)
    verified_sources_count: int = 0
    approval_status: str = "pending"
    handoff_path: list = field(default_factory=list)
    final_output: Any = None


def initial_context() -> ZoneAContext:
    return ZoneAContext()
