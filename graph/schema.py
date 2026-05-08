"""Pure graph schema projection for workflows and violation recurrence."""
from __future__ import annotations

from typing import Any

from zone_b.memory.violation_memory import recurrence_key


def _workflow_id(workflow: dict[str, Any] | str) -> str:
    if isinstance(workflow, str):
        return workflow
    return str(workflow.get("workflow_id") or workflow.get("id") or workflow.get("name") or "")


def _key(*parts: Any) -> str:
    return ":".join(str(part) for part in parts if str(part))


def _node(label: str, key: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {"label": label, "key": key, "properties": {"key": key, **properties}}


def _edge(
    edge_type: str,
    from_label: str,
    from_key: str,
    to_label: str,
    to_key: str,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    props = properties or {}
    return {
        "type": edge_type,
        "from_label": from_label,
        "from_key": from_key,
        "to_label": to_label,
        "to_key": to_key,
        "key": _key(from_key, edge_type, to_key),
        "properties": {"key": _key(from_key, edge_type, to_key), **props},
    }


def _topology_nodes(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    topology = workflow.get("declared_topology") or {}
    nodes = topology.get("nodes") if isinstance(topology, dict) else None
    return nodes if isinstance(nodes, list) else []


def _endpoint_lookup(workflow: dict[str, Any]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}

    def add(raw: dict[str, Any], default_kind: str) -> None:
        name = str(raw.get("name") or raw.get("id") or "")
        if not name:
            return
        kind = str(raw.get("kind") or default_kind)
        role = str(raw.get("role") or name.removesuffix("Agent").lower() or kind)
        item = {"name": name, "kind": kind, "role": role}
        lookup[name] = item
        if raw.get("id"):
            lookup[str(raw["id"])] = item

    for node in _topology_nodes(workflow):
        if isinstance(node, dict):
            add(node, str(node.get("kind") or "agent"))
    for agent in workflow.get("agents") or []:
        if isinstance(agent, dict):
            add(agent, "agent")
    for tool in workflow.get("tools") or []:
        if isinstance(tool, dict):
            add(tool, "tool")
    return lookup


def _entity_nodes(workflow: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    workflow_id = _workflow_id(workflow)
    lookup = _endpoint_lookup(workflow)
    nodes = [
        _node(
            "Tenant",
            tenant_id,
            {"tenant_id": tenant_id, "name": tenant_id},
        ),
        _node(
            "Workflow",
            _key(tenant_id, workflow_id),
            {
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "name": workflow.get("name", workflow_id),
                "owner": workflow.get("owner", ""),
            },
        ),
    ]
    seen = {(node["label"], node["key"]) for node in nodes}
    for entity in lookup.values():
        kind = entity["kind"]
        label = "Tool" if kind == "tool" else "Gate" if kind == "gate" else "Agent"
        key = _key(tenant_id, workflow_id, entity["name"])
        marker = (label, key)
        if marker in seen:
            continue
        seen.add(marker)
        nodes.append(
            _node(
                label,
                key,
                {
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "name": entity["name"],
                    "role": entity["role"],
                    "kind": kind,
                },
            )
        )
    for contract in workflow.get("contracts") or []:
        if not isinstance(contract, dict) or not contract.get("id"):
            continue
        contract_id = str(contract["id"])
        nodes.append(
            _node(
                "Contract",
                _key(tenant_id, workflow_id, contract_id),
                {
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "contract_id": contract_id,
                    "contract_type": str(contract.get("type", "")),
                    "rule": str(contract.get("rule", "")),
                },
            )
        )
    return nodes


def _node_label_for_kind(kind: str) -> str:
    if kind == "tool":
        return "Tool"
    if kind == "gate":
        return "Gate"
    return "Agent"


def _base_edges(workflow: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    workflow_id = _workflow_id(workflow)
    workflow_key = _key(tenant_id, workflow_id)
    edges = [
        _edge("Owns", "Tenant", tenant_id, "Workflow", workflow_key, {"tenant_id": tenant_id}),
    ]
    lookup = _endpoint_lookup(workflow)
    seen_entity_links: set[tuple[str, str]] = set()
    for entity in lookup.values():
        label = _node_label_for_kind(entity["kind"])
        entity_key = _key(tenant_id, workflow_id, entity["name"])
        rel = "HasTool" if label == "Tool" else "HasGate" if label == "Gate" else "HasAgent"
        marker = (rel, entity_key)
        if marker in seen_entity_links:
            continue
        seen_entity_links.add(marker)
        edges.append(
            _edge(
                rel,
                "Workflow",
                workflow_key,
                label,
                entity_key,
                {"tenant_id": tenant_id, "workflow_id": workflow_id},
            )
        )
    for contract in workflow.get("contracts") or []:
        if not isinstance(contract, dict) or not contract.get("id"):
            continue
        edges.append(
            _edge(
                "HasContract",
                "Workflow",
                workflow_key,
                "Contract",
                _key(tenant_id, workflow_id, contract["id"]),
                {"tenant_id": tenant_id, "workflow_id": workflow_id},
            )
        )
    return edges


def _topology_edges(workflow: dict[str, Any], tenant_id: str) -> list[dict[str, Any]]:
    workflow_id = _workflow_id(workflow)
    topology = workflow.get("declared_topology") or {}
    raw_edges = topology.get("edges") if isinstance(topology, dict) else None
    if not isinstance(raw_edges, list):
        return []
    lookup = _endpoint_lookup(workflow)
    edges: list[dict[str, Any]] = []
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict):
            continue
        source = lookup.get(str(raw_edge.get("from", "")))
        target = lookup.get(str(raw_edge.get("to", "")))
        if not source or not target:
            continue
        kind = str(raw_edge.get("kind") or "handoff")
        rel = "ToolCall" if kind == "tool_call" or target["kind"] == "tool" else "Handoff"
        edges.append(
            _edge(
                rel,
                _node_label_for_kind(source["kind"]),
                _key(tenant_id, workflow_id, source["name"]),
                _node_label_for_kind(target["kind"]),
                _key(tenant_id, workflow_id, target["name"]),
                {
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "declared": bool(raw_edge.get("declared", True)),
                    "kind": kind,
                },
            )
        )
    return edges


def build_workflow_graph_projection(
    workflow: dict[str, Any],
    tenant_id: str = "local",
) -> dict[str, list[dict[str, Any]]]:
    """Build the graph nodes and edges for a workflow registration."""
    return {
        "nodes": _entity_nodes(workflow, tenant_id),
        "edges": [*_base_edges(workflow, tenant_id), *_topology_edges(workflow, tenant_id)],
    }


def build_violation_graph_projection(
    *,
    workflow_id: str,
    run_id: str,
    violations: list[dict[str, Any]],
    tenant_id: str = "local",
) -> dict[str, list[dict[str, Any]]]:
    workflow_key = _key(tenant_id, workflow_id)
    run_key = _key(tenant_id, workflow_id, run_id)
    nodes = [
        _node(
            "Run",
            run_key,
            {"tenant_id": tenant_id, "workflow_id": workflow_id, "run_id": run_id},
        )
    ]
    edges = [
        _edge(
            "HasRun",
            "Workflow",
            workflow_key,
            "Run",
            run_key,
            {"tenant_id": tenant_id, "workflow_id": workflow_id},
        )
    ]
    seen: set[str] = set()
    for violation in violations:
        key = recurrence_key(violation)
        if not key or key in seen:
            continue
        seen.add(key)
        violation_key = _key(tenant_id, workflow_id, key)
        failed_agent = str(violation.get("failed_agent") or "")
        nodes.append(
            _node(
                "Violation",
                violation_key,
                {
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "recurrence_key": key,
                    "contract_type": str(violation.get("contract_type") or violation.get("type") or "").lower(),
                    "rule": str(violation.get("rule") or violation.get("title") or ""),
                    "failed_agent": failed_agent,
                    "severity": str(violation.get("severity", "")),
                },
            )
        )
        edges.append(
            _edge(
                "Observed",
                "Run",
                run_key,
                "Violation",
                violation_key,
                {"tenant_id": tenant_id, "workflow_id": workflow_id, "run_id": run_id},
            )
        )
        edges.append(
            _edge(
                "HasViolation",
                "Workflow",
                workflow_key,
                "Violation",
                violation_key,
                {"tenant_id": tenant_id, "workflow_id": workflow_id},
            )
        )
        if failed_agent:
            edges.append(
                _edge(
                    "Triggered",
                    "Agent",
                    _key(tenant_id, workflow_id, failed_agent),
                    "Violation",
                    violation_key,
                    {"tenant_id": tenant_id, "workflow_id": workflow_id},
                )
            )
    return {"nodes": nodes, "edges": edges}
