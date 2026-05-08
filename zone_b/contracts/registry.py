"""Canonical contract registry."""
from __future__ import annotations

from .checks import (
    check_approval_contract,
    check_evidence_contract,
    check_routing_contract,
    check_schema_contract,
    check_tool_contract,
)
from .types import Contract

DEFAULT_CONTRACTS: list[Contract] = [
    Contract(
        id="C-EVD",
        type="evidence",
        severity="high",
        rule_text="verified_sources_count must be > 0 before ReporterAgent runs",
        failed_agent="VerifierAgent",
        check_callable=check_evidence_contract,
    ),
    Contract(
        id="C-TOL",
        type="tool",
        severity="high",
        rule_text="VerifierAgent must record a tool_call_id (Tavily or Daytona)",
        failed_agent="VerifierAgent",
        check_callable=check_tool_contract,
    ),
    Contract(
        id="C-APR",
        type="approval",
        severity="high",
        rule_text="ActionAgent requires approval_status == approved before running",
        failed_agent="ActionAgent",
        check_callable=check_approval_contract,
    ),
    Contract(
        id="C-RTE",
        type="routing",
        severity="medium",
        rule_text=(
            "ReporterAgent requires a successful VerifierAgent tool event; "
            "ActionAgent requires HumanGate first"
        ),
        failed_agent="ReporterAgent",
        check_callable=check_routing_contract,
    ),
    Contract(
        id="C-SCH",
        type="schema",
        severity="medium",
        rule_text="final_output must include summary, claims, citations, risks, and next_steps",
        failed_agent="ReporterAgent",
        check_callable=check_schema_contract,
    ),
]

CONTRACT_REGISTRY: dict[str, Contract] = {
    contract.id: contract for contract in DEFAULT_CONTRACTS
}

CONTRACTS_BY_TYPE: dict[str, Contract] = {
    contract.type: contract for contract in DEFAULT_CONTRACTS
}
