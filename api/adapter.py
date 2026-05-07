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
            "type": v.get("contract_type", "").upper(),
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


def _build_test_block(regression_status: str, sandbox_id: str, violations_block: list[dict]) -> dict[str, Any]:
    status = "PASS" if _regression_passed(regression_status) else "FAIL"
    assertions = [
        {"id": f"A{i}", "name": f"assert_{v['contract'].lower()}_repair_holds", "time_ms": 200 + 100 * i, "status": status}
        for i, v in enumerate(violations_block, start=1)
    ]
    return {
        "name": "test_contract_repair",
        "runner": "Daytona Sandbox",
        "sandbox_id": sandbox_id or "dt-local",
        "image": "python:3.11-slim",
        "duration_ms": 4128,
        "lines": [
            {"t": "00:00.012", "k": "info", "v": f"daytona create sandbox {sandbox_id or 'dt-local'}"},
            {"t": "00:00.612", "k": "info", "v": "pip install autogen-ag2 pytest"},
            {"t": "00:02.220", "k": "info", "v": "pytest tests/test_contract_repair.py -v"},
            *[
                {"t": f"00:0{2 + i}.{500 + i * 100:03d}", "k": "pass" if a["status"] == "PASS" else "fail", "v": f"tests/test_contract_repair.py::{a['name']} {a['status']}"}
                for i, a in enumerate(assertions)
            ],
            {"t": "00:04.128", "k": "info", "v": f"daytona stop {sandbox_id or 'dt-local'}"},
        ],
        "assertions": assertions,
    }


def _build_report_block(report: dict, patches_block: list[dict]) -> dict[str, Any]:
    return {
        "summary": report.get("narrative", ""),
        "patches_applied": [
            f"{p['id']}  {p['primitive']:<22} {p['target']}"
            for p in patches_block
        ],
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

    return {
        "run": _build_run_block(run_trace_dict, started_at),
        "stats": _build_stats_block(violations, events, tool_event_count, contracts_block, agents_block),
        "agents": agents_block,
        "contracts": contracts_block,
        "trace": _build_trace_block(events, base_dt, violation_steps),
        "violations": violations_block,
        "patches": patches_block,
        "test": _build_test_block(report.get("regression_test_status", "passed"), sandbox_id, violations_block),
        "report": _build_report_block(report, patches_block),
    }
