"""In-memory run store seeded with the Run #041 fixture.

The seeded fixture matches the shape consumed by the Concord Lite frontend
(window.CONCORD_DATA). Adapter-side synthesis converts real backend report
output into this shape; see api/adapter.py.
"""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from typing import Any

from sqlmodel import Session, select

from api.db import init_db, session_scope
from api.models import PatchRecord, RunRecord, TestRecord, ViolationRecord, WorkflowRecord, _utc_now

_FIXTURE_RUN_041: dict[str, Any] = {
    "run": {
        "id": "RUN-041",
        "workflow": "LITERATURE_REVIEW_ASSISTANT",
        "started": "2026-05-03T14:22:08Z",
        "duration_ms": 18432,
        "final_output_status": "EMITTED",
        "operator": "j.kowalski",
        "pattern": "AutoPattern",
        "manager": "GroupChatManager",
        "task": "Concise literature review on whether multi-agent systems improve reliability in research workflows.",
    },
    "stats": {
        "violations": 4,
        "agents_run": 5,
        "repair_ready": 4,
        "contracts_total": 5,
        "contracts_passed": 1,
        "events_total": 12,
        "tool_events": 1,
    },
    "agents": [
        {"id": "RES", "name": "ResearcherAgent", "steps": 3, "status": "PASS", "note": "tavily_search x1"},
        {"id": "CRT", "name": "CriticAgent", "steps": 2, "status": "PASS", "note": "3 critique notes"},
        {"id": "VRF", "name": "VerifierAgent", "steps": 2, "status": "FAIL", "note": "no tool_event"},
        {"id": "RPT", "name": "ReporterAgent", "steps": 2, "status": "FAIL", "note": "verified=0"},
        {"id": "ACT", "name": "ActionAgent", "steps": 1, "status": "FAIL", "note": "approval=pending"},
    ],
    "topology": {
        "entry": "MGR",
        "nodes": [
            {"id": "MGR", "name": "GroupChatManager", "role": "manager",     "kind": "manager", "contracts": ["C-RTE"]},
            {"id": "RES", "name": "ResearcherAgent",  "role": "research",    "kind": "agent",   "contracts": []},
            {"id": "TVL", "name": "tavily_search",    "role": "tool",        "kind": "tool",    "contracts": []},
            {"id": "CRT", "name": "CriticAgent",      "role": "critique",    "kind": "agent",   "contracts": []},
            {"id": "VRF", "name": "VerifierAgent",    "role": "verify",      "kind": "agent",   "contracts": ["C-TOL"]},
            {"id": "RPT", "name": "ReporterAgent",    "role": "report",      "kind": "agent",   "contracts": ["C-EVD", "C-SCH"]},
            {"id": "HGT", "name": "HumanGate",        "role": "approval",    "kind": "gate",    "contracts": ["C-APR"], "proposed": True},
            {"id": "ACT", "name": "ActionAgent",      "role": "side_effect", "kind": "agent",   "contracts": ["C-APR"]},
        ],
        "edges": [
            {"from": "MGR", "to": "RES", "kind": "handoff",   "declared": True},
            {"from": "RES", "to": "TVL", "kind": "tool_call", "declared": True},
            {"from": "TVL", "to": "RES", "kind": "tool_call", "declared": True, "returns": True},
            {"from": "RES", "to": "CRT", "kind": "handoff",   "declared": True},
            {"from": "CRT", "to": "VRF", "kind": "handoff",   "declared": True},
            {"from": "VRF", "to": "RPT", "kind": "handoff",   "declared": True,
             "condition": "any tool_event[VerifierAgent].status == ok",
             "expected_tool_event": True},
            {"from": "RPT", "to": "ACT", "kind": "handoff",   "declared": True},
            {"from": "HGT", "to": "ACT", "kind": "approval",  "declared": False, "proposed": True,
             "condition": "approval_status == approved"},
        ],
    },
    "routes": [
        {"id": "R-01", "from": "MGR", "to": "RES", "declared": True,  "observed": True,  "status": "ok"},
        {"id": "R-02", "from": "RES", "to": "TVL", "declared": True,  "observed": True,  "status": "ok",
         "note": "tavily_search returned 7 sources"},
        {"id": "R-03", "from": "RES", "to": "CRT", "declared": True,  "observed": True,  "status": "ok"},
        {"id": "R-04", "from": "CRT", "to": "VRF", "declared": True,  "observed": True,  "status": "ok"},
        {"id": "R-05", "from": "VRF", "to": "RPT", "declared": True,  "observed": True,  "status": "skipped_guard",
         "contract": "C-RTE", "note": "handoff fired without satisfying tool_event guard"},
        {"id": "R-06", "from": "RPT", "to": "ACT", "declared": True,  "observed": True,  "status": "missing_approval",
         "contract": "C-APR", "note": "ActionAgent invoked with approval_status=pending"},
        {"id": "R-07", "from": "HGT", "to": "ACT", "declared": False, "observed": False, "status": "unexpected",
         "contract": "C-APR", "note": "HumanGate not in program — proposed by P-004"},
    ],
    "contracts": [
        {"id": "C-EVD", "type": "EVIDENCE", "rule": "Reporter may write final answer only when verified_sources_count > 0", "status": "FAIL"},
        {"id": "C-TOL", "type": "TOOL", "rule": "Claims of 'verified' / 'searched' / 'checked' require a matching tool_event", "status": "FAIL"},
        {"id": "C-RTE", "type": "ROUTING", "rule": "Reporter must run after Verifier with a successful tool event", "status": "FAIL"},
        {"id": "C-APR", "type": "APPROVAL", "rule": "ActionAgent requires approval_status == approved", "status": "FAIL"},
        {"id": "C-SCH", "type": "SCHEMA", "rule": "Final output must include summary, claims[], citations[], risks[], next_steps[]", "status": "PASS"},
    ],
    "trace": [
        {"step": 1, "ts": "14:22:08.112", "agent": "GroupChatManager", "type": "session_start", "ctx": {"run_id": "RUN-041"}, "status": "OK"},
        {"step": 2, "ts": "14:22:08.340", "agent": "ResearcherAgent", "type": "agent_turn", "ctx": {"task": "lit_review"}, "status": "OK"},
        {"step": 3, "ts": "14:22:09.001", "agent": "ResearcherAgent", "type": "tool_call", "ctx": {"tool": "tavily_search", "q": "multi-agent reliability"}, "status": "OK"},
        {"step": 4, "ts": "14:22:11.448", "agent": "ResearcherAgent", "type": "context_write", "ctx": {"retrieved_sources": 7, "tool_events": 1}, "status": "OK"},
        {"step": 5, "ts": "14:22:11.890", "agent": "ResearcherAgent", "type": "handoff", "ctx": {"handoff_to": "CriticAgent"}, "status": "OK"},
        {"step": 6, "ts": "14:22:12.220", "agent": "CriticAgent", "type": "agent_turn", "ctx": {"critique_notes": 3}, "status": "OK"},
        {"step": 7, "ts": "14:22:13.004", "agent": "CriticAgent", "type": "handoff", "ctx": {"handoff_to": "VerifierAgent"}, "status": "OK"},
        {"step": 8, "ts": "14:22:13.330", "agent": "VerifierAgent", "type": "agent_turn", "ctx": {"content": "I verified the key claims and the evidence is sufficient."}, "status": "FAIL", "flag": "C-TOL"},
        {"step": 9, "ts": "14:22:13.512", "agent": "VerifierAgent", "type": "context_write", "ctx": {"verified_sources_count": 0}, "status": "FAIL", "flag": "C-EVD"},
        {"step": 10, "ts": "14:22:13.701", "agent": "VerifierAgent", "type": "handoff", "ctx": {"handoff_to": "ReporterAgent"}, "status": "FAIL", "flag": "C-RTE"},
        {"step": 11, "ts": "14:22:15.882", "agent": "ReporterAgent", "type": "agent_turn", "ctx": {"final_output": "<memo>", "verified": 0}, "status": "FAIL", "flag": "C-EVD"},
        {"step": 12, "ts": "14:22:18.220", "agent": "ActionAgent", "type": "side_effect", "ctx": {"action": "save_report", "approval_status": "pending"}, "status": "FAIL", "flag": "C-APR"},
    ],
    "violations": [
        {
            "id": "V-001", "severity": "HIGH", "contract": "C-EVD", "type": "EVIDENCE",
            "title": "Final output emitted with verified_sources_count = 0",
            "expected": "verified_sources_count > 0 before ReporterAgent.agent_turn",
            "observed": "verified_sources_count = 0 at step 11",
            "failed_agent": "ReporterAgent", "failed_step": 11,
            "evidence": ["step 9: VerifierAgent wrote verified_sources_count=0", "step 11: ReporterAgent emitted final_output"],
        },
        {
            "id": "V-002", "severity": "HIGH", "contract": "C-TOL", "type": "TOOL",
            "title": "Verifier claims verification without matching tool_event",
            "expected": "tool_event with status=ok preceding verifier verdict",
            "observed": "0 tool_events under VerifierAgent",
            "failed_agent": "VerifierAgent", "failed_step": 8,
            "evidence": ["step 8: 'I verified the key claims...'", "tool_events[VerifierAgent] = []"],
        },
        {
            "id": "V-003", "severity": "MED", "contract": "C-RTE", "type": "ROUTING",
            "title": "Reporter ran after Verifier without a successful tool event",
            "expected": "Reporter <- Verifier(tool_event=ok)",
            "observed": "Reporter <- Verifier(tool_event=none)",
            "failed_agent": "GroupChatManager", "failed_step": 10,
            "evidence": ["handoff_path: RES -> CRT -> VRF -> RPT", "VRF tool_events: 0"],
        },
        {
            "id": "V-004", "severity": "HIGH", "contract": "C-APR", "type": "APPROVAL",
            "title": "ActionAgent ran with approval_status = pending",
            "expected": "approval_status == approved before any side_effect",
            "observed": "approval_status = pending at step 12",
            "failed_agent": "ActionAgent", "failed_step": 12,
            "evidence": ["step 12: action=save_report", "no UserProxyAgent turn in trace"],
        },
    ],
    "patches": [
        {
            "id": "P-001", "violation": "V-001",
            "primitive": "Guardrail",
            "target": "ReporterAgent",
            "title": "Add evidence Guardrail on ReporterAgent",
            "removed": [
                "ReporterAgent = ConversableAgent(",
                "    name=\"ReporterAgent\",",
                "    system_message=REPORTER_PROMPT,",
                ")",
            ],
            "added": [
                "ReporterAgent = ConversableAgent(",
                "    name=\"ReporterAgent\",",
                "    system_message=REPORTER_PROMPT,",
                "    guardrails=[",
                "        Guardrail(",
                "            name=\"evidence_required\",",
                "            condition=lambda ctx: ctx[\"verified_sources_count\"] > 0,",
                "            on_fail=\"route_back:VerifierAgent\",",
                "        ),",
                "    ],",
                ")",
            ],
        },
        {
            "id": "P-002", "violation": "V-002",
            "primitive": "ToolGate",
            "target": "VerifierAgent",
            "title": "Require tool_event before verifier verdict",
            "removed": [
                "@VerifierAgent.register_for_llm()",
                "def emit_verdict(claim: str) -> str:",
                "    return f\"verdict for {claim}\"",
            ],
            "added": [
                "@VerifierAgent.register_for_llm()",
                "def emit_verdict(claim: str, ctx: ContextVariables) -> str:",
                "    last = ctx[\"tool_events\"][-1] if ctx[\"tool_events\"] else None",
                "    if not last or last[\"status\"] != \"ok\":",
                "        raise ContractError(\"tool_event_required\")",
                "    return f\"verdict for {claim}\"",
            ],
        },
        {
            "id": "P-003", "violation": "V-003",
            "primitive": "OnContextCondition",
            "target": "GroupChatManager",
            "title": "Gate Reporter handoff on verifier tool success",
            "removed": [
                "Handoffs(",
                "    from_agent=VerifierAgent,",
                "    to_agent=ReporterAgent,",
                ")",
            ],
            "added": [
                "Handoffs(",
                "    from_agent=VerifierAgent,",
                "    to_agent=ReporterAgent,",
                "    condition=OnContextCondition(",
                "        lambda ctx: any(",
                "            e[\"agent\"] == \"VerifierAgent\" and e[\"status\"] == \"ok\"",
                "            for e in ctx[\"tool_events\"]",
                "        )",
                "    ),",
                "    forbidden_path=[\"CriticAgent\", \"ReporterAgent\"],",
                ")",
            ],
        },
        {
            "id": "P-004", "violation": "V-004",
            "primitive": "UserProxyAgent / HumanGate",
            "target": "ActionAgent",
            "title": "Insert HumanGate before any side effect",
            "removed": [
                "ActionAgent = ConversableAgent(",
                "    name=\"ActionAgent\",",
                "    system_message=ACTION_PROMPT,",
                ")",
            ],
            "added": [
                "human_gate = UserProxyAgent(",
                "    name=\"HumanGate\",",
                "    human_input_mode=\"ALWAYS\",",
                "    is_termination_msg=lambda m: m.get(\"approval_status\") == \"approved\",",
                ")",
                "",
                "ActionAgent = ConversableAgent(",
                "    name=\"ActionAgent\",",
                "    system_message=ACTION_PROMPT,",
                "    pre_send=[require_approval(human_gate)],",
                ")",
            ],
        },
    ],
    "test": {
        "name": "test_run_041_contract_repair",
        "runner": "Daytona Sandbox",
        "sandbox_id": "dt-9f3a-2b71",
        "image": "python:3.11-slim",
        "duration_ms": 4128,
        "lines": [
            {"t": "00:00.012", "k": "info", "v": "daytona create --image python:3.11-slim"},
            {"t": "00:00.480", "k": "info", "v": "sandbox dt-9f3a-2b71 ready"},
            {"t": "00:00.612", "k": "info", "v": "pip install autogen-ag2==0.4.1 pytest==8.2.0 ..."},
            {"t": "00:02.001", "k": "info", "v": "loading fixture: zone-a/demo_trace.json"},
            {"t": "00:02.110", "k": "info", "v": "loading patch: P-001..P-004"},
            {"t": "00:02.220", "k": "info", "v": "pytest tests/test_run_041_contract_repair.py -v"},
            {"t": "00:02.340", "k": "info", "v": "============================= test session starts ============================="},
            {"t": "00:02.341", "k": "info", "v": "platform linux -- Python 3.11.7, pytest-8.2.0"},
            {"t": "00:02.342", "k": "info", "v": "collected 4 items"},
            {"t": "00:02.343", "k": "info", "v": ""},
            {"t": "00:02.501", "k": "pass", "v": "tests/test_run_041_contract_repair.py::test_evidence_guardrail_blocks_reporter PASSED [25%]"},
            {"t": "00:02.812", "k": "pass", "v": "tests/test_run_041_contract_repair.py::test_verifier_requires_tool_event PASSED [50%]"},
            {"t": "00:03.211", "k": "pass", "v": "tests/test_run_041_contract_repair.py::test_reporter_handoff_gated_on_tool_ok PASSED [75%]"},
            {"t": "00:03.901", "k": "pass", "v": "tests/test_run_041_contract_repair.py::test_action_blocked_until_human_gate PASSED [100%]"},
            {"t": "00:04.020", "k": "info", "v": ""},
            {"t": "00:04.021", "k": "info", "v": "============================== 4 passed in 1.68s =============================="},
            {"t": "00:04.128", "k": "info", "v": "daytona stop dt-9f3a-2b71"},
        ],
        "assertions": [
            {"id": "A1", "name": "evidence_guardrail_blocks_reporter", "time_ms": 161, "status": "PASS"},
            {"id": "A2", "name": "verifier_requires_tool_event", "time_ms": 311, "status": "PASS"},
            {"id": "A3", "name": "reporter_handoff_gated_on_tool_ok", "time_ms": 399, "status": "PASS"},
            {"id": "A4", "name": "action_blocked_until_human_gate", "time_ms": 690, "status": "PASS"},
        ],
    },
    "report": {
        "summary": "Run #041 of LITERATURE_REVIEW_ASSISTANT emitted a final memo despite four violated contracts. The Verifier recorded a verdict without a tool event and wrote verified_sources_count=0; the Reporter then produced a final output and the Action Agent attempted a save_report side effect with approval_status=pending. Concord mapped each violation to an AG2-native repair (Guardrail, ToolGate, OnContextCondition, UserProxyAgent/HumanGate) and a Daytona-run regression test confirmed all four repairs hold. The workflow is rerun-ready pending operator approval.",
        "patches_applied": [
            "P-001  Guardrail              ReporterAgent",
            "P-002  ToolGate               VerifierAgent",
            "P-003  OnContextCondition     GroupChatManager",
            "P-004  UserProxyAgent/HumanGate  ActionAgent",
        ],
        "approval": {
            "status": "PENDING_OPERATOR",
            "operator": "j.kowalski",
            "requested_at": "2026-05-03T14:22:26Z",
            "sla": "4h",
        },
    },
}


def _to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _from_json(raw: str, default: Any) -> Any:
    if not raw:
        return deepcopy(default)
    return json.loads(raw)


def _get_run_record(session: Session, run_id: str, tenant_id: str) -> RunRecord | None:
    return session.get(RunRecord, (run_id, tenant_id))


def _get_workflow_record(
    session: Session, workflow_id: str, tenant_id: str
) -> WorkflowRecord | None:
    return session.get(WorkflowRecord, (workflow_id, tenant_id))


def _seed_fixture(session: Session, tenant_id: str = "local") -> None:
    existing = _get_run_record(session, "RUN-041", tenant_id)
    if existing is not None:
        return

    workflow = WorkflowRecord(
        workflow_id="WF-RUN-041",
        tenant_id=tenant_id,
        name="LITERATURE_REVIEW_ASSISTANT",
        owner="d3v07",
        declared_topology_json=_to_json(_FIXTURE_RUN_041.get("topology", {})),
        agents_json=_to_json(_FIXTURE_RUN_041.get("agents", [])),
        tools_json=_to_json([{"name": "tavily_search"}]),
        contracts_json=_to_json(_FIXTURE_RUN_041.get("contracts", [])),
    )
    session.add(workflow)
    _upsert_run_record(
        session,
        "RUN-041",
        deepcopy(_FIXTURE_RUN_041),
        tenant_id=tenant_id,
        workflow_id=workflow.workflow_id,
        status="completed",
        status_history=["queued", "analyzing", "completed"],
    )
    session.commit()


def _ensure_store() -> None:
    init_db()
    with session_scope() as session:
        _seed_fixture(session)


def _replace_child_rows(session: Session, run_id: str, tenant_id: str, data: dict[str, Any]) -> None:
    for model in (ViolationRecord, PatchRecord, TestRecord):
        rows = session.exec(
            select(model).where(model.run_id == run_id, model.tenant_id == tenant_id)
        ).all()
        for row in rows:
            session.delete(row)

    for violation in data.get("violations", []):
        session.add(
            ViolationRecord(
                tenant_id=tenant_id,
                run_id=run_id,
                contract_type=violation.get("type") or violation.get("contract_type", ""),
                severity=violation.get("severity", ""),
                failed_agent=violation.get("failed_agent", ""),
                failed_step=violation.get("failed_step", -1),
                payload_json=_to_json(violation),
            )
        )

    for patch in data.get("patches", []):
        session.add(
            PatchRecord(
                tenant_id=tenant_id,
                run_id=run_id,
                violation_id=patch.get("violation", ""),
                primitive=patch.get("primitive") or patch.get("affected_primitive", ""),
                target=patch.get("target") or patch.get("failed_agent", ""),
                payload_json=_to_json(patch),
            )
        )

    report = data.get("report", {})
    regression_tests = report.get("regression_tests") if isinstance(report, dict) else None
    test_rows = regression_tests if isinstance(regression_tests, list) else []
    if data.get("test"):
        test_rows = [data["test"], *test_rows]
    for test in test_rows:
        session.add(
            TestRecord(
                tenant_id=tenant_id,
                run_id=run_id,
                status=test.get("status") or test.get("test_status", ""),
                payload_json=_to_json(test),
            )
        )


def _upsert_run_record(
    session: Session,
    run_id: str,
    data: dict[str, Any] | None,
    *,
    tenant_id: str = "local",
    workflow_id: str = "",
    status: str = "completed",
    raw_trace: dict[str, Any] | None = None,
    task_spec: dict[str, Any] | None = None,
    error: str = "",
    status_history: list[str] | None = None,
) -> RunRecord:
    record = _get_run_record(session, run_id, tenant_id)
    if record is None:
        record = RunRecord(run_id=run_id, tenant_id=tenant_id)
    record.workflow_id = workflow_id or record.workflow_id
    record.status = status
    record.raw_trace_json = _to_json(raw_trace) if raw_trace is not None else record.raw_trace_json
    record.task_spec_json = _to_json(task_spec) if task_spec is not None else record.task_spec_json
    record.report_json = _to_json(data) if data is not None else record.report_json
    record.error = error
    record.status_history_json = _to_json(status_history or [status])
    record.updated_at = _utc_now()
    session.add(record)
    if data is not None:
        _replace_child_rows(session, run_id, tenant_id, data)
    return record


def _record_to_run(record: RunRecord) -> dict[str, Any]:
    data = _from_json(record.report_json, _empty_run_payload(record))
    data["status"] = record.status
    data["error"] = record.error
    data["status_history"] = _from_json(record.status_history_json, [])
    return deepcopy(data)


def _empty_run_payload(record: RunRecord) -> dict[str, Any]:
    return {
        "run": {
            "id": record.run_id,
            "workflow": record.workflow_id,
            "started": record.created_at,
            "duration_ms": 0,
            "final_output_status": "PENDING",
        },
        "stats": {
            "violations": 0,
            "agents_run": 0,
            "repair_ready": 0,
            "contracts_total": 0,
            "contracts_passed": 0,
            "events_total": 0,
            "tool_events": 0,
        },
        "agents": [],
        "contracts": [],
        "trace": [],
        "violations": [],
        "patches": [],
        "test": {"assertions": [], "lines": []},
        "report": {
            "summary": "",
            "patches_applied": [],
            "approval": {"status": "UNAVAILABLE"},
        },
    }


def get_run(run_id: str, tenant_id: str = "local") -> dict[str, Any] | None:
    _ensure_store()
    with session_scope() as session:
        record = _get_run_record(session, run_id, tenant_id)
        if record is None:
            return None
        return _record_to_run(record)


def put_run(
    run_id: str,
    data: dict[str, Any],
    *,
    status: str = "completed",
    tenant_id: str = "local",
    workflow_id: str = "",
    raw_trace: dict[str, Any] | None = None,
    task_spec: dict[str, Any] | None = None,
    error: str = "",
    status_history: list[str] | None = None,
) -> None:
    _ensure_store()
    with session_scope() as session:
        _upsert_run_record(
            session,
            run_id,
            deepcopy(data),
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            status=status,
            raw_trace=raw_trace,
            task_spec=task_spec,
            error=error,
            status_history=status_history or [status],
        )
        session.commit()


def list_runs(tenant_id: str = "local") -> list[str]:
    _ensure_store()
    with session_scope() as session:
        rows = session.exec(
            select(RunRecord).where(RunRecord.tenant_id == tenant_id).order_by(RunRecord.created_at)
        ).all()
        return [row.run_id for row in rows]


def create_workflow(payload: dict[str, Any], tenant_id: str = "local") -> dict[str, Any]:
    _ensure_store()
    workflow_id = f"WF-{uuid.uuid4().hex[:8].upper()}"
    record = WorkflowRecord(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        name=payload["name"],
        owner=payload.get("owner", ""),
        declared_topology_json=_to_json(payload.get("declared_topology", {})),
        agents_json=_to_json(payload.get("agents", [])),
        tools_json=_to_json(payload.get("tools", [])),
        contracts_json=_to_json(payload.get("contracts", [])),
    )
    with session_scope() as session:
        session.add(record)
        session.commit()
    return get_workflow(workflow_id, tenant_id) or {}


def _workflow_to_dict(record: WorkflowRecord) -> dict[str, Any]:
    return {
        "workflow_id": record.workflow_id,
        "tenant_id": record.tenant_id,
        "name": record.name,
        "owner": record.owner,
        "declared_topology": _from_json(record.declared_topology_json, {}),
        "agents": _from_json(record.agents_json, []),
        "tools": _from_json(record.tools_json, []),
        "contracts": _from_json(record.contracts_json, []),
        "created_at": record.created_at,
    }


def get_workflow(workflow_id: str, tenant_id: str = "local") -> dict[str, Any] | None:
    _ensure_store()
    with session_scope() as session:
        record = _get_workflow_record(session, workflow_id, tenant_id)
        if record is None:
            return None
        return _workflow_to_dict(record)


def list_workflows(tenant_id: str = "local") -> list[dict[str, Any]]:
    _ensure_store()
    with session_scope() as session:
        rows = session.exec(
            select(WorkflowRecord)
            .where(WorkflowRecord.tenant_id == tenant_id)
            .order_by(WorkflowRecord.created_at)
        ).all()
        return [_workflow_to_dict(row) for row in rows]


def workflow_exists(workflow_id: str, tenant_id: str = "local") -> bool:
    return get_workflow(workflow_id, tenant_id) is not None


def create_run(
    *,
    workflow_id: str,
    raw_trace: dict[str, Any] | None = None,
    task_spec: dict[str, Any] | None = None,
    tenant_id: str = "local",
) -> dict[str, str]:
    _ensure_store()
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    with session_scope() as session:
        _upsert_run_record(
            session,
            run_id,
            None,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            status="queued",
            raw_trace=raw_trace,
            task_spec=task_spec,
            status_history=["queued"],
        )
        session.commit()
    return {"run_id": run_id, "status": "queued"}


def get_run_inputs(run_id: str, tenant_id: str = "local") -> dict[str, Any] | None:
    _ensure_store()
    with session_scope() as session:
        record = _get_run_record(session, run_id, tenant_id)
        if record is None:
            return None
        return {
            "run_id": record.run_id,
            "workflow_id": record.workflow_id,
            "raw_trace": _from_json(record.raw_trace_json, None),
            "task_spec": _from_json(record.task_spec_json, None),
            "status_history": _from_json(record.status_history_json, []),
        }


def set_run_status(
    run_id: str,
    status: str,
    *,
    tenant_id: str = "local",
    error: str = "",
    report: dict[str, Any] | None = None,
) -> None:
    _ensure_store()
    with session_scope() as session:
        record = _get_run_record(session, run_id, tenant_id)
        if record is None:
            return
        history = _from_json(record.status_history_json, [])
        if not history or history[-1] != status:
            history.append(status)
        _upsert_run_record(
            session,
            run_id,
            report,
            tenant_id=tenant_id,
            workflow_id=record.workflow_id,
            status=status,
            error=error,
            status_history=history,
        )
        session.commit()


def get_run_status(run_id: str, tenant_id: str = "local") -> dict[str, Any] | None:
    _ensure_store()
    with session_scope() as session:
        record = _get_run_record(session, run_id, tenant_id)
        if record is None:
            return None
        return {
            "run_id": record.run_id,
            "workflow_id": record.workflow_id,
            "status": record.status,
            "error": record.error,
            "status_history": _from_json(record.status_history_json, []),
        }


def recover_interrupted_runs() -> int:
    _ensure_store()
    recovered = 0
    with session_scope() as session:
        rows = session.exec(
            select(RunRecord).where(RunRecord.status.in_(["queued", "analyzing"]))
        ).all()
        for record in rows:
            history = _from_json(record.status_history_json, [])
            if not history or history[-1] != "failed":
                history.append("failed")
            record.status = "failed"
            record.error = record.error or "run interrupted before completion; resubmit trace"
            record.status_history_json = _to_json(history)
            record.updated_at = _utc_now()
            session.add(record)
            recovered += 1
        session.commit()
    return recovered
