"""YAML parser for workflow contracts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .registry import CONTRACTS_BY_TYPE
from .types import Contract

SUPPORTED_CONTRACT_TYPES = tuple(CONTRACTS_BY_TYPE)
REQUIRED_FIELDS = {"id", "type", "rule"}


class ContractDslError(ValueError):
    """Raised when contract YAML cannot be normalized."""


def load_contracts_yaml(path: Path) -> list[Contract]:
    return parse_contracts_yaml(path.read_text())


def parse_contracts_yaml(source: str) -> list[Contract]:
    if not source.strip():
        raise ContractDslError("contracts_yaml line 1: contracts_yaml must not be empty")

    try:
        root_node = yaml.compose(source, Loader=yaml.SafeLoader)
        data = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        raise ContractDslError(_yaml_error_message(exc)) from exc

    if not isinstance(data, dict):
        raise ContractDslError("contracts_yaml line 1: root must be a mapping")

    contracts_node = _mapping_value_node(root_node, "contracts")
    if contracts_node is None:
        raise ContractDslError("contracts_yaml line 1: missing required field: contracts")

    raw_contracts = data.get("contracts")
    entries = _contract_entries(raw_contracts, contracts_node)
    seen_types: set[str] = set()
    contracts: list[Contract] = []
    for label, raw_contract, line in entries:
        if not isinstance(raw_contract, dict):
            raise ContractDslError(f"contracts_yaml line {line}: {label} must be a mapping")
        normalized = dict(raw_contract)
        if "type" not in normalized and not label.startswith("contracts["):
            normalized["type"] = label.removeprefix("contracts.")
        contract_type = _normalize_type(normalized.get("type"), label, line)
        normalized["type"] = contract_type
        if contract_type in seen_types:
            raise ContractDslError(
                f"contracts_yaml line {line}: duplicate contract type \"{contract_type}\"; "
                "only one contract per supported type is allowed"
            )
        seen_types.add(contract_type)

        missing = sorted(REQUIRED_FIELDS - set(normalized))
        if missing:
            raise ContractDslError(
                f"contracts_yaml line {line}: {label} missing required field(s): {', '.join(missing)}"
            )
        _validate_machine_fields(normalized, contracts_node, label, line)

        reference = CONTRACTS_BY_TYPE[contract_type]
        dsl_fields = {
            key: value
            for key, value in normalized.items()
            if key not in {"id", "type", "severity", "rule", "failed_agent"}
        }
        contracts.append(
            Contract(
                id=str(normalized["id"]),
                type=contract_type,
                severity=str(normalized.get("severity") or reference.severity).lower(),
                rule_text=str(normalized["rule"]),
                failed_agent=str(normalized.get("failed_agent") or reference.failed_agent),
                check_callable=reference.check_callable,
                dsl=dsl_fields,
            )
        )

    return contracts


def _yaml_error_message(exc: yaml.YAMLError) -> str:
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    if mark is None:
        return f"contracts_yaml: {exc}"
    problem = getattr(exc, "problem", None) or exc.__class__.__name__
    return f"contracts_yaml line {mark.line + 1}, column {mark.column + 1}: {problem}"


def _mapping_value_node(node, key: str):
    if node is None or not isinstance(node, yaml.MappingNode):
        return None
    for key_node, value_node in node.value:
        if key_node.value == key:
            return value_node
    return None


def _contract_entries(raw_contracts: Any, contracts_node) -> list[tuple[str, dict[str, Any], int]]:
    if isinstance(raw_contracts, list):
        if not isinstance(contracts_node, yaml.SequenceNode):
            raise ContractDslError("contracts_yaml line 1: contracts must be a sequence")
        entries = []
        for index, item in enumerate(raw_contracts):
            item_node = contracts_node.value[index]
            entries.append((f"contracts[{index}]", item, item_node.start_mark.line + 1))
        return entries

    if isinstance(raw_contracts, dict):
        if not isinstance(contracts_node, yaml.MappingNode):
            raise ContractDslError("contracts_yaml line 1: contracts must be a mapping")
        entries = []
        for key_node, value_node in contracts_node.value:
            line = key_node.start_mark.line + 1
            if key_node.tag != "tag:yaml.org,2002:str":
                raise ContractDslError(
                    f"contracts_yaml line {line}: contract type key must be a string"
                )
            key = key_node.value
            entries.append((f"contracts.{key}", raw_contracts[key], line))
        return entries

    line = getattr(getattr(contracts_node, "start_mark", None), "line", 0) + 1
    raise ContractDslError(f"contracts_yaml line {line}: contracts must be a mapping or sequence")


def _normalize_type(raw_type: Any, label: str, line: int) -> str:
    if raw_type is None:
        raise ContractDslError(f"contracts_yaml line {line}: {label} missing required field(s): type")
    if not isinstance(raw_type, str):
        raise ContractDslError(f"contracts_yaml line {line}: {label}.type must be a string")
    contract_type = raw_type.lower()
    if contract_type not in CONTRACTS_BY_TYPE:
        expected = ", ".join(SUPPORTED_CONTRACT_TYPES)
        raise ContractDslError(
            f"contracts_yaml line {line}: unknown contract type \"{raw_type}\"; expected {expected}"
        )
    return contract_type


def _validate_machine_fields(contract: dict[str, Any], contracts_node, label: str, line: int) -> None:
    if contract["type"] == "schema":
        output = contract.get("output")
        if output is not None and not isinstance(output, dict):
            key_line = _nested_key_line(contracts_node, label, ["output"], line)
            raise ContractDslError(
                f"contracts_yaml line {key_line}: schema.output must be a mapping"
            )
        required_keys = (output or {}).get("required_keys")
        if required_keys is not None and not isinstance(required_keys, list):
            key_line = _nested_key_line(contracts_node, label, ["output", "required_keys"], line)
            raise ContractDslError(
                f"contracts_yaml line {key_line}: schema.output.required_keys must be a YAML sequence"
            )

    if contract["type"] == "approval":
        requires = contract.get("requires")
        if requires is not None and not isinstance(requires, dict):
            key_line = _nested_key_line(contracts_node, label, ["requires"], line)
            raise ContractDslError(
                f"contracts_yaml line {key_line}: approval.requires must be a mapping"
            )
        eq_value = (requires or {}).get("approval_status", {})
        if eq_value is not None and not isinstance(eq_value, dict):
            key_line = _nested_key_line(
                contracts_node,
                label,
                ["requires", "approval_status"],
                line,
            )
            raise ContractDslError(
                f"contracts_yaml line {key_line}: approval.requires.approval_status must be a mapping"
            )
        if isinstance(eq_value, dict) and "eq" in eq_value and not isinstance(eq_value["eq"], str):
            key_line = _nested_key_line(
                contracts_node,
                label,
                ["requires", "approval_status", "eq"],
                line,
            )
            raise ContractDslError(
                f"contracts_yaml line {key_line}: approval.requires.approval_status.eq must be a scalar string"
            )


def _nested_key_line(contracts_node, label: str, keys: list[str], default_line: int) -> int:
    node = _entry_node(contracts_node, label)
    for key in keys:
        node = _mapping_value_node(node, key)
        if node is None:
            return default_line
    return node.start_mark.line + 1


def _entry_node(contracts_node, label: str):
    if label.startswith("contracts[") and isinstance(contracts_node, yaml.SequenceNode):
        index = int(label.removeprefix("contracts[").removesuffix("]"))
        return contracts_node.value[index]
    if label.startswith("contracts.") and isinstance(contracts_node, yaml.MappingNode):
        key = label.removeprefix("contracts.")
        for key_node, value_node in contracts_node.value:
            if str(key_node.value) == key:
                return value_node
    return contracts_node
