"""FalkorDB persistence boundary for workflow graph projections."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from graph.queries import projection_upsert_queries
from graph.schema import build_violation_graph_projection, build_workflow_graph_projection


class GraphPersistenceError(RuntimeError):
    """Raised when graph persistence is enabled but FalkorDB is unavailable."""


def _truthy(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def graph_enabled() -> bool:
    return _truthy(os.environ.get("CONCORD_GRAPH_ENABLED")) or bool(os.environ.get("FALKORDB_HOST"))


def _graph_name_for_tenant(tenant_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", tenant_id).strip("_") or "local"
    return f"concord_{normalized}"


def _settings(tenant_id: str) -> dict[str, Any]:
    return {
        "name": os.environ.get("FALKORDB_GRAPH") or _graph_name_for_tenant(tenant_id),
        "host": os.environ.get("FALKORDB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("FALKORDB_PORT", "6379")),
        "username": os.environ.get("FALKORDB_USERNAME") or None,
        "password": os.environ.get("FALKORDB_PASSWORD") or None,
    }


def _query_engine(tenant_id: str) -> Any:
    settings = _settings(tenant_id)
    try:
        from autogen.agentchat.contrib.graph_rag.falkor_graph_query_engine import (
            FalkorGraphQueryEngine,
        )
    except ImportError as exc:
        raise GraphPersistenceError("AG2 FalkorGraphQueryEngine is unavailable") from exc
    try:
        return FalkorGraphQueryEngine(**settings)
    except ImportError as exc:
        try:
            from falkordb import FalkorDB
        except ImportError as falkor_exc:
            raise GraphPersistenceError("FalkorDB Python client is unavailable") from falkor_exc
        return _DirectFalkorEngine(
            name=settings["name"],
            falkordb=FalkorDB(
                host=settings["host"],
                port=settings["port"],
                username=settings["username"],
                password=settings["password"],
            ),
            ag2_import_error=str(exc),
        )


@dataclass
class _DirectFalkorEngine:
    name: str
    falkordb: Any
    ag2_import_error: str


class FalkorTopologyGraph:
    def __init__(self, tenant_id: str) -> None:
        self.query_engine = _query_engine(tenant_id)
        self.graph = self.query_engine.falkordb.select_graph(self.query_engine.name)

    def upsert_projection(self, projection: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        nodes = 0
        edges = 0
        for query, params in projection_upsert_queries(projection):
            self.graph.query(query, params=params)
            if query.startswith("MERGE (n:"):
                nodes += 1
            else:
                edges += 1
        return {"nodes": nodes, "edges": edges}


def persist_workflow_topology(workflow: dict[str, Any], tenant_id: str = "local") -> dict[str, Any]:
    if not graph_enabled():
        return {"enabled": False, "nodes": 0, "edges": 0}
    projection = build_workflow_graph_projection(workflow, tenant_id=tenant_id)
    counts = FalkorTopologyGraph(tenant_id).upsert_projection(projection)
    return {"enabled": True, **counts}


def persist_run_violations(
    *,
    workflow_id: str,
    run_id: str,
    violations: list[dict[str, Any]],
    tenant_id: str = "local",
) -> dict[str, Any]:
    if not graph_enabled() or not violations:
        return {"enabled": graph_enabled(), "nodes": 0, "edges": 0}
    projection = build_violation_graph_projection(
        workflow_id=workflow_id,
        run_id=run_id,
        violations=violations,
        tenant_id=tenant_id,
    )
    counts = FalkorTopologyGraph(tenant_id).upsert_projection(projection)
    return {"enabled": True, **counts}
