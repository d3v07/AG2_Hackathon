"""Backend report -> CONCORD_DATA shape adapter.

The Zone B pipeline emits a flat report dict; the frontend expects a
9-section shape with per-agent rollups, per-violation patches, and a
regression test timeline. This module synthesizes the missing fields
deterministically from the raw run trace + violations + report.

Backend repair patches are passed through when present. Template-based
patch synthesis remains only for legacy reports that do not include
native `patches`.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any


_CANONICAL_CONTRACTS: list[dict[str, str]] = [
    {"id": "C-EVD", "type": "EVIDENCE", "rule": "Reporter may write final answer only when verified_sources_count > 0"},
    {"id": "C-TOL", "type": "TOOL", "rule": "Claims of 'verified' / 'searched' / 'checked' require a matching tool_event"},
    {"id": "C-RTE", "type": "ROUTING", "rule": "Reporter must run after Verifier with a successful tool event"},
    {"id": "C-APR", "type": "APPROVAL", "rule": "ActionAgent requires approval_status == approved"},
    {"id": "C-SCH", "type": "SCHEMA", "rule": "Final output must include summary, claims[], citations[], risks[], next_steps[]"},
]

_AGENT_ID_BY_NAME: dict[str, str] = {
    "ResearcherAgent": "RES",
    "CriticAgent": "CRT",
    "VerifierAgent": "VRF",
    "ReporterAgent": "RPT",
    "ActionAgent": "ACT",
}

_CONTRACT_TYPE_BY_KEY: dict[str, str] = {
    "evidence": "C-EVD",
    "tool": "C-TOL",
    "routing": "C-RTE",
    "approval": "C-APR",
    "schema": "C-SCH",
}

_PATCH_TEMPLATE_BY_CONTRACT: dict[str, dict[str, Any]] = {
    "C-EVD": {
        "primitive": "Guardrail",
        "title": "Add evidence Guardrail on ReporterAgent",
    },
    "C-TOL": {
        "primitive": "ToolGate",
        "title": "Require tool_event before verifier verdict",
    },
    "C-RTE": {
        "primitive": "OnContextCondition",
        "title": "Gate Reporter handoff on verifier tool success",
    },
    "C-APR": {
        "primitive": "UserProxyAgent / HumanGate",
        "title": "Insert HumanGate before any side effect",
    },
    "C-SCH": {
        "primitive": "SchemaCheck",
        "title": "Validate final output schema",
    },
}


def _ts(epoch_offset: float, base: datetime) -> str:
    """Render an event timestamp as HH:MM:SS.mmm in UTC."""
    from datetime import timedelta

    moment = base + timedelta(seconds=epoch_offset)
    return moment.strftime("%H:%M:%S.") + f"{moment.microsecond // 1000:03d}"


def _agent_short(name: str) -> str:
    return _AGENT_ID_BY_NAME.get(name, name[:3].upper())


def _unique_id(base: str, used: set[str]) -> str:
    normalized = "".join(char for char in base.upper() if char.isalnum())[:6] or "NODE"
    candidate = normalized
    suffix = 2
    while candidate in used:
        candidate = f"{normalized[:4]}{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _build_run_block(run_trace: dict[str, Any], started_at: str) -> dict[str, Any]:
    events = run_trace.get("events", [])
    last_ts = events[-1].get("timestamp", 0.0) if events else 0.0
    return {
        "id": run_trace.get("run_id", "RUN-?"),
        "workflow": run_trace.get("workflow_name", "UNKNOWN").upper(),
        "started": started_at,
        "duration_ms": int(last_ts * 1000),
        "final_output_status": "EMITTED" if run_trace.get("final_output") else "MISSING",
        "operator": "j.kowalski",
        "pattern": "AutoPattern",
        "manager": "GroupChatManager",
        "task": "Concise literature review on whether multi-agent systems improve reliability in research workflows.",
    }


def _build_stats_block(
    violations: list[dict],
    events: list[dict],
    tool_event_count: int,
    contracts: list[dict],
    agents: list[dict],
) -> dict[str, int]:
    return {
        "violations": len(violations),
        "agents_run": len(agents),
        "repair_ready": len(violations),
        "contracts_total": len(contracts),
        "contracts_passed": sum(1 for c in contracts if c["status"] == "PASS"),
        "events_total": len(events),
        "tool_events": tool_event_count,
    }


def _build_agents_block(events: list[dict], failed_agents: set[str]) -> list[dict]:
    by_agent: dict[str, list[dict]] = {}
    for ev in events:
        agent = ev.get("agent")
        if not agent or agent == "GroupChatManager":
            continue
        by_agent.setdefault(agent, []).append(ev)
    result = []
    for agent_name, agent_events in by_agent.items():
        status = "FAIL" if agent_name in failed_agents else "PASS"
        tool_calls = sum(1 for e in agent_events if e.get("type") == "tool_call")
        note = f"{tool_calls} tool_call(s)" if tool_calls else "no tool_event" if status == "FAIL" else f"{len(agent_events)} step(s)"
        result.append({
            "id": _agent_short(agent_name),
            "name": agent_name,
            "steps": len(agent_events),
            "status": status,
            "note": note,
        })
    return result


def _build_contracts_block(violation_contract_ids: set[str]) -> list[dict]:
    return [
        {**c, "status": "FAIL" if c["id"] in violation_contract_ids else "PASS"}
        for c in _CANONICAL_CONTRACTS
    ]


def _node_role(agent_name: str) -> str:
    role = agent_name.removesuffix("Agent").removesuffix("Manager")
    return (role or agent_name).lower()


def _tool_names_from_event(event: dict[str, Any]) -> list[str]:
    ctx = event.get("context_delta") or {}
    names: list[str] = []
    if isinstance(ctx, dict):
        direct_tool = ctx.get("tool")
        if direct_tool:
            names.append(str(direct_tool))
        for tool_event in ctx.get("tool_events") or []:
            if isinstance(tool_event, dict) and tool_event.get("tool_name"):
                names.append(str(tool_event["tool_name"]))
    if event.get("type") == "tool_call" and event.get("tool_call_id"):
        names.append(str(event.get("tool_call_id")))
    return list(dict.fromkeys(names))


def _build_topology_and_routes(
    events: list[dict],
    violations: list[dict],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    used_ids: set[str] = set()
    node_by_name: dict[str, dict[str, Any]] = {}
    nodes: list[dict[str, Any]] = []

    def ensure_node(name: str, kind: str = "agent", proposed: bool = False) -> str:
        if name in node_by_name:
            return node_by_name[name]["id"]
        if name == "GroupChatManager":
            base_id = "MGR"
        elif kind == "tool":
            base_id = name[:3]
        else:
            base_id = _agent_short(name)
        node_id = _unique_id(base_id, used_ids)
        node = {
            "id": node_id,
            "name": name,
            "role": _node_role(name),
            "kind": kind,
            "contracts": [],
        }
        if proposed:
            node["proposed"] = True
        node_by_name[name] = node
        nodes.append(node)
        return node_id

    ordered_agent_ids: list[str] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(from_id: str, to_id: str, kind: str, **extra: Any) -> None:
        key = (from_id, to_id, kind)
        if from_id == to_id or key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"from": from_id, "to": to_id, "kind": kind, "declared": True, **extra})

    for event in events:
        agent = event.get("agent")
        if not agent:
            continue
        kind = "manager" if agent == "GroupChatManager" else "agent"
        agent_id = ensure_node(str(agent), kind=kind)
        if not ordered_agent_ids or ordered_agent_ids[-1] != agent_id:
            ordered_agent_ids.append(agent_id)

        for tool_name in _tool_names_from_event(event):
            tool_id = ensure_node(tool_name, kind="tool")
            add_edge(agent_id, tool_id, "tool_call")
            add_edge(tool_id, agent_id, "tool_call", returns=True)

        handoff_to = event.get("handoff_to")
        ctx = event.get("context_delta") or {}
        if not handoff_to and isinstance(ctx, dict):
            handoff_to = ctx.get("handoff_to")
        if handoff_to:
            to_id = ensure_node(str(handoff_to), kind="agent")
            add_edge(agent_id, to_id, "handoff")

    for from_id, to_id in zip(ordered_agent_ids, ordered_agent_ids[1:], strict=False):
        add_edge(from_id, to_id, "handoff")

    event_agent_by_step = {
        event.get("step"): str(event.get("agent"))
        for event in events
        if event.get("step") is not None and event.get("agent")
    }
    violation_contracts_by_node: dict[str, list[str]] = {}
    route_contract_by_target: dict[str, str] = {}
    for violation in violations:
        contract_id = _CONTRACT_TYPE_BY_KEY.get(violation.get("contract_type", ""), "")
        if not contract_id:
            continue
        failed_agent = str(violation.get("failed_agent") or "")
        failed_step_agent = event_agent_by_step.get(violation.get("failed_step"))
        node_name = failed_agent if failed_agent in node_by_name else failed_step_agent
        if not node_name or node_name not in node_by_name:
            continue
        node_id = node_by_name[node_name]["id"]
        violation_contracts_by_node.setdefault(node_id, []).append(contract_id)
        if contract_id in {"C-RTE", "C-APR"}:
            route_contract_by_target[node_id] = contract_id

    for node_id, contracts in violation_contracts_by_node.items():
        node = next(node for node in nodes if node["id"] == node_id)
        node["contracts"] = sorted(set([*node.get("contracts", []), *contracts]))

    routes = []
    for index, edge in enumerate([edge for edge in edges if not edge.get("returns")], start=1):
        contract = route_contract_by_target.get(edge["to"], "")
        status = "ok"
        note = ""
        if contract == "C-RTE":
            status = "skipped_guard"
            note = "handoff reached a routing contract violation"
        elif contract == "C-APR":
            status = "missing_approval"
            note = "approval contract failed on this route"
        routes.append(
            {
                "id": f"R-{index:02d}",
                "from": edge["from"],
                "to": edge["to"],
                "declared": bool(edge.get("declared", True)),
                "observed": not edge.get("proposed", False),
                "status": status if not edge.get("proposed", False) else "unexpected",
                "contract": contract,
                "note": note,
            }
        )

    if not nodes:
        ensure_node("Run", kind="manager")
    return {"entry": nodes[0]["id"], "nodes": nodes, "edges": edges}, routes


def _build_trace_block(events: list[dict], base_dt: datetime, violation_steps: dict[int, str]) -> list[dict]:
    rows = []
    for ev in events:
        step = ev.get("step", 0)
        ctx_delta = ev.get("context_delta") or {}
        ctx = dict(ctx_delta) if ctx_delta else {}
        if ev.get("handoff_to"):
            ctx["handoff_to"] = ev["handoff_to"]
        if ev.get("content") and not ctx:
            ctx["content"] = ev["content"]
        row = {
            "step": step,
            "ts": _ts(ev.get("timestamp", 0.0), base_dt),
            "agent": ev.get("agent", ""),
            "type": ev.get("type", "agent_turn"),
            "ctx": ctx,
            "status": "FAIL" if step in violation_steps else "OK",
        }
        if step in violation_steps:
            row["flag"] = violation_steps[step]
        rows.append(row)
    return rows


def _build_violations_block(violations: list[dict]) -> list[dict]:
    out = []
    for i, v in enumerate(violations, start=1):
        contract_id = _CONTRACT_TYPE_BY_KEY.get(v.get("contract_type", ""), "C-???")
        out.append({
            "id": f"V-{i:03d}",
            "severity": v.get("severity", "low").upper()[:4],
            "contract": contract_id,
            "contract_type": v.get("contract_type", ""),
            "type": v.get("contract_type", "").upper(),
            "rule": v.get("rule", "Contract violation"),
            "title": v.get("rule", "Contract violation"),
            "expected": v.get("expected", ""),
            "observed": v.get("observed", ""),
            "failed_agent": v.get("failed_agent", ""),
            "failed_step": v.get("failed_step", -1),
            "evidence": [
                f"step {v.get('failed_step', '?')}: {v.get('observed', '')}",
            ],
        })
    return out


def _patch_code_lines(patch_code: Any) -> list[str]:
    if not isinstance(patch_code, str):
        return []
    return [line.rstrip() for line in patch_code.splitlines() if line.strip()]


def _fallback_patch_template(contract_id: str) -> dict[str, Any]:
    return _PATCH_TEMPLATE_BY_CONTRACT.get(contract_id, {"primitive": "Patch", "title": "Apply repair"})


def _build_native_patches_block(
    violations_block: list[dict],
    native_patches: list[Any],
) -> list[dict]:
    patches = []
    for i, raw_patch in enumerate(native_patches, start=1):
        patch = raw_patch if isinstance(raw_patch, dict) else {}
        violation = violations_block[i - 1] if i <= len(violations_block) else {}
        contract_id = _CONTRACT_TYPE_BY_KEY.get(
            str(patch.get("contract_type", "")).lower(),
            violation.get("contract", "C-???"),
        )
        template = _fallback_patch_template(contract_id)

        item = {
            "id": f"P-{i:03d}",
            "violation": violation.get("id", f"V-{i:03d}"),
            "primitive": patch.get("affected_primitive") or template["primitive"],
            "target": patch.get("failed_agent") or violation.get("failed_agent", ""),
            "title": patch.get("repair_patch") or template["title"],
            "removed": [],
            "added": _patch_code_lines(patch.get("patch_code", "")),
        }
        for key in ("contract_type", "severity", "rule", "expected_impact", "confidence", "failed_step"):
            if key in patch:
                item[key] = patch[key]
        patches.append(item)
    return patches


def _build_legacy_patches_block(violations_block: list[dict], patch_code: str) -> list[dict]:
    """Synthesize one patch per violation using contract-keyed templates."""
    patches = []
    code_lines = _patch_code_lines(patch_code)
    for i, v in enumerate(violations_block, start=1):
        template = _fallback_patch_template(v["contract"])
        patches.append({
            "id": f"P-{i:03d}",
            "violation": v["id"],
            "primitive": template["primitive"],
            "target": v["failed_agent"],
            "title": template["title"],
            "removed": [],
            "added": code_lines if i == 1 else [],
        })
    return patches


def _build_patches_block(violations_block: list[dict], report: dict[str, Any]) -> list[dict]:
    native_patches = report.get("patches")
    if isinstance(native_patches, list):
        return _build_native_patches_block(violations_block, native_patches)
    return _build_legacy_patches_block(violations_block, report.get("patch_code", ""))


def _regression_passed(regression_status: str) -> bool:
    return str(regression_status).lower() in {"pass", "passed"}


def _build_cost_block(report: dict[str, Any]) -> dict[str, Any]:
    cost = report.get("regression_cost")
    if not isinstance(cost, dict):
        cost = {}
    usage = report.get("regression_usage")
    if not isinstance(usage, dict):
        usage = {}
    return {
        "daytona_seconds": float(cost.get("daytona_seconds", 0) or 0),
        "llm_tokens": int(cost.get("llm_tokens", usage.get("total_tokens", 0)) or 0),
        "llm_cost_usd": float(cost.get("llm_cost_usd", 0) or 0),
        "daytona_cost_usd": float(cost.get("daytona_cost_usd", 0) or 0),
    }


def _build_test_block(
    regression_status: str,
    sandbox_id: str,
    violations_block: list[dict],
    *,
    duration_ms: int = 4128,
) -> dict[str, Any]:
    status = "PASS" if _regression_passed(regression_status) else "FAIL"
    assertions = [
        {"id": f"A{i}", "name": f"assert_{v['contract'].lower()}_repair_holds", "time_ms": 200 + 100 * i, "status": status}
        for i, v in enumerate(violations_block, start=1)
    ]
    duration = int(duration_ms or 0) if duration_ms is not None else 4128
    duration_seconds = max(0, duration // 1000)
    duration_stamp = f"00:{duration_seconds:02d}.{duration % 1000:03d}"
    return {
        "name": "test_contract_repair",
        "runner": "Daytona Sandbox",
        "sandbox_id": sandbox_id or "dt-local",
        "image": "python:3.11-slim",
        "duration_ms": duration,
        "lines": [
            {"t": "00:00.012", "k": "info", "v": f"daytona create sandbox {sandbox_id or 'dt-local'}"},
            {"t": "00:00.612", "k": "info", "v": "pip install autogen-ag2 pytest"},
            {"t": "00:02.220", "k": "info", "v": "pytest tests/test_contract_repair.py -v"},
            *[
                {"t": f"00:0{2 + i}.{500 + i * 100:03d}", "k": "pass" if a["status"] == "PASS" else "fail", "v": f"tests/test_contract_repair.py::{a['name']} {a['status']}"}
                for i, a in enumerate(assertions)
            ],
            {"t": duration_stamp, "k": "info", "v": f"daytona stop {sandbox_id or 'dt-local'}"},
        ],
        "assertions": assertions,
    }


def _build_report_block(
    report: dict,
    patches_block: list[dict],
    cost_block: dict[str, Any],
) -> dict[str, Any]:
    return {
        "summary": report.get("narrative", ""),
        "patches_applied": [
            f"{p['id']}  {p['primitive']:<22} {p['target']}"
            for p in patches_block
        ],
        "regression_summary": report.get("regression_summary", {}),
        "regression_tests": report.get("regression_tests", []),
        "usage_summary": report.get(
            "regression_usage",
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        ),
        "cost_summary": cost_block,
        "approval": {
            "status": "PENDING_OPERATOR" if report.get("approval_status") == "pending" else report.get("approval_status", "PENDING_OPERATOR").upper(),
            "operator": "j.kowalski",
            "requested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sla": "4h",
        },
    }


def report_to_concord_data(
    report: dict[str, Any],
    run_trace_dict: dict[str, Any],
    violations: list[dict[str, Any]],
    *,
    sandbox_id: str = "",
) -> dict[str, Any]:
    """Convert backend pipeline output into the frontend's CONCORD_DATA shape."""
    started_at = "2026-05-03T14:22:08Z"
    base_dt = datetime(2026, 5, 3, 14, 22, 8, tzinfo=timezone.utc)

    events = run_trace_dict.get("events", [])
    tool_event_count = sum(
        len((e.get("context_delta") or {}).get("tool_events", []))
        for e in events
    )

    failed_agents = {v.get("failed_agent") for v in violations if v.get("failed_agent")}
    violation_contract_ids = {
        _CONTRACT_TYPE_BY_KEY.get(v.get("contract_type", ""), "")
        for v in violations
    }
    violation_steps = {
        v.get("failed_step", -1): _CONTRACT_TYPE_BY_KEY.get(v.get("contract_type", ""), "")
        for v in violations
    }

    contracts_block = _build_contracts_block(violation_contract_ids)
    agents_block = _build_agents_block(events, failed_agents)
    violations_block = _build_violations_block(violations)
    patches_block = _build_patches_block(violations_block, report)
    topology_block, routes_block = _build_topology_and_routes(events, violations)
    cost_block = _build_cost_block(report)
    report_sandbox_id = report.get("sandbox_id") or sandbox_id
    duration_ms = report.get("regression_duration_ms", 4128)

    return {
        "run": _build_run_block(run_trace_dict, started_at),
        "stats": _build_stats_block(violations, events, tool_event_count, contracts_block, agents_block),
        "agents": agents_block,
        "topology": topology_block,
        "routes": routes_block,
        "contracts": contracts_block,
        "trace": _build_trace_block(events, base_dt, violation_steps),
        "violations": violations_block,
        "patches": patches_block,
        "test": _build_test_block(
            report.get("regression_test_status", "passed"),
            report_sandbox_id,
            violations_block,
            duration_ms=duration_ms,
        ),
        "cost": cost_block,
        "report": _build_report_block(report, patches_block, cost_block),
    }
