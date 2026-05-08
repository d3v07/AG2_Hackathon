"""Graph schema tests for workflow topology persistence."""
from __future__ import annotations

from graph.schema import build_workflow_graph_projection


def _workflow() -> dict:
    return {
        "workflow_id": "WF-GRAPH",
        "name": "GraphWorkflow",
        "declared_topology": {
            "entry": "ResearcherAgent",
            "nodes": [
                {"id": "RES", "name": "ResearcherAgent", "kind": "agent", "role": "research"},
                {"id": "VRF", "name": "VerifierAgent", "kind": "agent", "role": "verify"},
                {"id": "TVL", "name": "tavily_search", "kind": "tool", "role": "search"},
            ],
            "edges": [
                {"from": "ResearcherAgent", "to": "VerifierAgent", "kind": "handoff"},
                {"from": "ResearcherAgent", "to": "tavily_search", "kind": "tool_call"},
            ],
        },
        "agents": [{"name": "ResearcherAgent"}, {"name": "VerifierAgent"}],
        "tools": [{"name": "tavily_search"}],
        "contracts": [
            {"id": "C-RTE", "type": "routing", "rule": "Verifier before Reporter"},
        ],
    }


def test_workflow_projection_contains_agent_tool_and_contract_nodes():
    projection = build_workflow_graph_projection(_workflow(), tenant_id="tenant-a")

    node_keys = {(node["label"], node["key"]) for node in projection["nodes"]}

    assert ("Tenant", "tenant-a") in node_keys
    assert ("Workflow", "tenant-a:WF-GRAPH") in node_keys
    assert ("Agent", "tenant-a:WF-GRAPH:ResearcherAgent") in node_keys
    assert ("Agent", "tenant-a:WF-GRAPH:VerifierAgent") in node_keys
    assert ("Tool", "tenant-a:WF-GRAPH:tavily_search") in node_keys
    assert ("Contract", "tenant-a:WF-GRAPH:C-RTE") in node_keys


def test_workflow_projection_creates_handoff_and_toolcall_edges():
    projection = build_workflow_graph_projection(_workflow(), tenant_id="tenant-a")

    edge_keys = {
        (edge["type"], edge["from_key"], edge["to_key"])
        for edge in projection["edges"]
    }

    assert (
        "Handoff",
        "tenant-a:WF-GRAPH:ResearcherAgent",
        "tenant-a:WF-GRAPH:VerifierAgent",
    ) in edge_keys
    assert (
        "ToolCall",
        "tenant-a:WF-GRAPH:ResearcherAgent",
        "tenant-a:WF-GRAPH:tavily_search",
    ) in edge_keys


def test_workflow_projection_keeps_queryable_handoff_shape():
    projection = build_workflow_graph_projection(_workflow(), tenant_id="tenant-a")

    handoff = next(edge for edge in projection["edges"] if edge["type"] == "Handoff")

    assert handoff["from_label"] == "Agent"
    assert handoff["to_label"] == "Agent"
    assert handoff["properties"]["workflow_id"] == "WF-GRAPH"
    assert handoff["properties"]["declared"] is True
