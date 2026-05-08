"""Cypher query generation for FalkorDB graph projections."""
from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _identifier(value: str) -> str:
    if not _IDENTIFIER.match(value):
        raise ValueError(f"invalid graph identifier: {value}")
    return value


def _set_clause(alias: str, properties: dict[str, Any]) -> str:
    names = [name for name in properties if name != "key"]
    if not names:
        return ""
    assignments = ", ".join(f"{alias}.{_identifier(name)} = ${name}" for name in names)
    return f" SET {assignments}"


def node_upsert_query(node: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    label = _identifier(str(node["label"]))
    properties = dict(node.get("properties") or {})
    properties["key"] = node["key"]
    query = f"MERGE (n:{label} {{key: $key}}){_set_clause('n', properties)}"
    return query, properties


def edge_upsert_query(edge: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    rel_type = _identifier(str(edge["type"]))
    from_label = _identifier(str(edge["from_label"]))
    to_label = _identifier(str(edge["to_label"]))
    properties = dict(edge.get("properties") or {})
    properties["key"] = edge["key"]
    params = {
        "from_key": edge["from_key"],
        "to_key": edge["to_key"],
        **properties,
    }
    query = (
        f"MATCH (a:{from_label} {{key: $from_key}}), (b:{to_label} {{key: $to_key}}) "
        f"MERGE (a)-[r:{rel_type} {{key: $key}}]->(b)"
        f"{_set_clause('r', properties)}"
    )
    return query, params


def projection_upsert_queries(
    projection: dict[str, list[dict[str, Any]]],
) -> Iterator[tuple[str, dict[str, Any]]]:
    for node in projection.get("nodes") or []:
        yield node_upsert_query(node)
    for edge in projection.get("edges") or []:
        yield edge_upsert_query(edge)
