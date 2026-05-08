"""YAML contract DSL tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from zone_b.contracts import CONTRACT_REGISTRY
from zone_b.contracts.parser import ContractDslError, load_contracts_yaml, parse_contracts_yaml
from zone_b.contracts.types import Contract


def test_literature_review_yaml_round_trips_existing_contracts():
    contracts = load_contracts_yaml(Path("zone_b/contracts/examples/literature_review.yaml"))

    assert all(isinstance(contract, Contract) for contract in contracts)
    assert [contract.id for contract in contracts] == list(CONTRACT_REGISTRY)
    for contract in contracts:
        reference = CONTRACT_REGISTRY[contract.id]
        assert contract.type == reference.type
        assert contract.severity == reference.severity
        assert contract.rule_text == reference.rule_text
        assert contract.failed_agent == reference.failed_agent
        assert contract.check_callable is reference.check_callable


def test_contract_yaml_parser_returns_normalized_dicts():
    contracts = parse_contracts_yaml(
        """
contracts:
  - id: C-EVD
    type: evidence
    severity: high
    rule: verified_sources_count must be > 0 before ReporterAgent runs
    failed_agent: VerifierAgent
"""
    )

    assert [contract.to_dict() for contract in contracts] == [
        {
            "id": "C-EVD",
            "type": "evidence",
            "severity": "high",
            "rule": "verified_sources_count must be > 0 before ReporterAgent runs",
            "failed_agent": "VerifierAgent",
        }
    ]


def test_contract_yaml_parser_preserves_machine_readable_fields():
    contracts = parse_contracts_yaml(
        """
contracts:
  approval:
    id: C-APR
    rule: ActionAgent requires approval_status == approved before running
    requires:
      approval_status:
        eq: approved
      human_gate:
        any_of: [HumanGate, HumanGateAgent]
"""
    )

    assert contracts[0].to_dict()["requires"] == {
        "approval_status": {"eq": "approved"},
        "human_gate": {"any_of": ["HumanGate", "HumanGateAgent"]},
    }


def test_contract_yaml_parser_reports_line_numbered_errors():
    with pytest.raises(ContractDslError) as exc_info:
        parse_contracts_yaml(
            """
contracts:
  - id: C-BAD
    type: evidence
"""
        )

    message = str(exc_info.value)
    assert "line 3" in message
    assert "contracts[0]" in message
    assert "missing required field(s)" in message


def test_contract_yaml_parser_rejects_unknown_contract_type():
    with pytest.raises(ContractDslError) as exc_info:
        parse_contracts_yaml(
            """
contracts:
  guardrail:
    id: C-GRD
    rule: Something custom
"""
        )

    assert "line 3" in str(exc_info.value)
    assert "unknown contract type" in str(exc_info.value)


def test_contract_yaml_parser_rejects_duplicate_contract_type():
    with pytest.raises(ContractDslError) as exc_info:
        parse_contracts_yaml(
            """
contracts:
  - id: C-RTE-A
    type: routing
    rule: Reporter must be gated
  - id: C-RTE-B
    type: ROUTING
    rule: Duplicate routing contract
"""
        )

    assert "line 6" in str(exc_info.value)
    assert "duplicate contract type" in str(exc_info.value)


def test_contract_yaml_parser_validates_schema_required_keys_shape():
    with pytest.raises(ContractDslError) as exc_info:
        parse_contracts_yaml(
            """
contracts:
  schema:
    id: C-SCH
    rule: Final output must include summary, claims, citations, risks, and next_steps
    output:
      object: final_output
      required_keys: summary
"""
        )

    assert "line 8" in str(exc_info.value)
    assert "required_keys must be a YAML sequence" in str(exc_info.value)


def test_contract_yaml_parser_rejects_non_string_mapping_keys():
    with pytest.raises(ContractDslError) as exc_info:
        parse_contracts_yaml(
            """
contracts:
  1:
    id: C-EVD
    rule: verified_sources_count must be > 0 before ReporterAgent runs
"""
        )

    assert "line 3" in str(exc_info.value)
    assert "contract type key must be a string" in str(exc_info.value)


def test_contract_yaml_parser_validates_schema_output_shape():
    with pytest.raises(ContractDslError) as exc_info:
        parse_contracts_yaml(
            """
contracts:
  schema:
    id: C-SCH
    rule: final_output must include summary, claims, citations, risks, and next_steps
    output: nope
"""
        )

    assert "line 6" in str(exc_info.value)
    assert "schema.output must be a mapping" in str(exc_info.value)


def test_contract_yaml_parser_validates_approval_status_shape():
    with pytest.raises(ContractDslError) as exc_info:
        parse_contracts_yaml(
            """
contracts:
  approval:
    id: C-APR
    rule: ActionAgent requires approval_status == approved before running
    requires:
      approval_status: approved
"""
        )

    assert "line 7" in str(exc_info.value)
    assert "approval.requires.approval_status must be a mapping" in str(exc_info.value)
