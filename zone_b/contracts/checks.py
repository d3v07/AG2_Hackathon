"""Deterministic contract predicates."""
from __future__ import annotations

from shared.models import ContextSnapshot, RunTrace

REQUIRED_FINAL_OUTPUT_KEYS = {"summary", "claims", "citations", "risks", "next_steps"}


def check_evidence_contract(_run_trace: RunTrace, snap: ContextSnapshot) -> bool:
    return snap.verified_sources_count > 0


def check_tool_contract(run_trace: RunTrace, _snap: ContextSnapshot) -> bool:
    return any(e.agent == "VerifierAgent" and e.tool_call_id for e in run_trace.events)


def check_approval_contract(_run_trace: RunTrace, snap: ContextSnapshot) -> bool:
    return snap.approval_status == "approved"


def _has_successful_verifier_tool_event(event) -> bool:
    if event.agent != "VerifierAgent":
        return False
    for tool_event in event.context_delta.get("tool_events") or []:
        status = getattr(tool_event, "status", None)
        if status is None and isinstance(tool_event, dict):
            status = tool_event.get("status")
        if status in {"success", "ok"}:
            return True
    return False


def check_routing_contract(run_trace: RunTrace, _snap: ContextSnapshot | None = None) -> bool:
    verifier_tool_seen = False
    human_gate_seen = False

    for event in sorted(run_trace.events, key=lambda e: e.step):
        if _has_successful_verifier_tool_event(event):
            verifier_tool_seen = True
        if event.agent in {"HumanGate", "HumanGateAgent"}:
            human_gate_seen = True
        if event.agent == "ReporterAgent" and not verifier_tool_seen:
            return False
        if event.agent == "ActionAgent" and not human_gate_seen:
            return False

    return True


def check_schema_contract(_run_trace: RunTrace | None, snap: ContextSnapshot) -> bool:
    if not isinstance(snap.final_output, dict):
        return False
    return REQUIRED_FINAL_OUTPUT_KEYS.issubset(snap.final_output.keys())
