from dataclasses import dataclass
from typing import Any


@dataclass
class ToolEvent:
    tool_name: str
    input: Any
    output: Any
    status: str        # "success" | "failure"
    evidence_id: str
    timestamp: float


@dataclass
class TraceEvent:
    step: int
    agent: str
    type: str          # "agent_turn" | "handoff" | "tool_call" | "context_update"
    content: str
    tool_call_id: str | None
    context_delta: dict
    handoff_to: str | None
    timestamp: float


@dataclass
class RunTrace:
    run_id: str
    workflow_name: str
    events: list[TraceEvent]
    final_output: Any


@dataclass
class ContextSnapshot:
    retrieved_sources: list
    verified_sources_count: int
    tool_events: list[ToolEvent]
    approval_status: str   # "pending" | "approved" | "rejected"
    failed_agent: str | None
    failed_step: int | None
    final_output: Any


@dataclass
class Violation:
    contract_type: str  # "evidence" | "tool" | "routing" | "approval" | "schema"
    severity: str       # "high" | "medium" | "low"
    rule: str
    expected: str
    observed: str
    failed_agent: str
    failed_step: int


@dataclass
class RoleContract:
    agent_name: str
    allowed_actions: list[str]
    required_inputs: list[str]
    forbidden_outputs: list[str]


@dataclass
class EvidenceContract:
    claim_type: str
    required_source_count: int
    required_tool_event: str


@dataclass
class RouteContract:
    from_agent: str
    to_agent: str
    condition: str
    forbidden_path: list[str]


@dataclass
class ApprovalContract:
    side_effect: str
    required_approval_state: str
    human_gate: str
