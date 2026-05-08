"""Contract registry tests."""
from __future__ import annotations

from zone_b.agents.contract_checker import CONTRACTS
from zone_b.contracts import CONTRACT_REGISTRY, DEFAULT_CONTRACTS
from zone_b.contracts.types import Contract


def test_contract_checker_loads_dataclass_contracts_from_registry():
    assert CONTRACTS == DEFAULT_CONTRACTS
    assert all(isinstance(contract, Contract) for contract in CONTRACTS)
    assert [contract.id for contract in CONTRACTS] == [
        "C-EVD",
        "C-TOL",
        "C-APR",
        "C-RTE",
        "C-SCH",
    ]


def test_contract_registry_indexes_by_id():
    assert set(CONTRACT_REGISTRY) == {"C-EVD", "C-TOL", "C-APR", "C-RTE", "C-SCH"}
    assert CONTRACT_REGISTRY["C-EVD"].type == "evidence"
    assert CONTRACT_REGISTRY["C-TOL"].severity == "high"
    assert CONTRACT_REGISTRY["C-RTE"].failed_agent == "ReporterAgent"
