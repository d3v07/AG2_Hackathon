"""API persistence tests for the SQLModel-backed store."""
from __future__ import annotations


def _configure_db(tmp_path):
    from api.db import configure_database, init_db

    db_url = f"sqlite:///{tmp_path / 'concord.db'}"
    configure_database(db_url)
    init_db()
    return db_url


def test_seeded_run_persists_across_store_reinitialization(tmp_path):
    from api.db import configure_database, init_db
    from api.store import get_run, list_runs

    db_url = _configure_db(tmp_path)

    first = get_run("RUN-041")
    assert first is not None
    assert first["run"]["id"] == "RUN-041"
    assert first["cost"]["daytona_seconds"] > 0
    assert first["test"]["validation_state"] == "passed"
    assert first["report"]["validation_state"] == "passed"
    assert "RUN-041" in list_runs()

    configure_database(db_url)
    init_db()

    restarted = get_run("RUN-041")
    assert restarted is not None
    assert restarted["run"]["id"] == "RUN-041"
    assert len(restarted["patches"]) == 4
    assert restarted["test"]["assertions"][0]["validation_state"] == "passed"
    assert restarted["report"]["validation_summary"]["passed"] == 4
    assert restarted["cost"]["daytona_cost_usd"] > 0
    routing = [
        item
        for item in restarted["recurrences"]
        if item["recurrence_key"]
        == "routing|GroupChatManager|Reporter ran after Verifier without a successful tool event"
    ]
    assert routing[0]["count"] == 3
    assert routing[0]["edge"] == {"from": "VRF", "to": "RPT"}


def test_put_run_survives_new_engine_for_same_database(tmp_path):
    from api.db import configure_database, init_db
    from api.store import get_run, put_run

    db_url = _configure_db(tmp_path)
    put_run(
        "RUN-PERSISTED",
        {
            "run": {"id": "RUN-PERSISTED", "workflow": "TEST"},
            "patches": [],
            "violations": [],
            "report": {"approval": {"status": "PENDING_OPERATOR"}},
        },
        status="completed",
    )

    configure_database(db_url)
    init_db()

    assert get_run("RUN-PERSISTED")["run"]["id"] == "RUN-PERSISTED"


def test_every_persistence_table_declares_tenant_id():
    from api.models import PatchRecord, RunRecord, TestRecord, ViolationRecord, WorkflowRecord

    for model in (WorkflowRecord, RunRecord, ViolationRecord, PatchRecord, TestRecord):
        assert "tenant_id" in model.model_fields


def test_same_run_id_is_isolated_by_tenant(tmp_path):
    from api.store import get_run, put_run

    _configure_db(tmp_path)
    put_run(
        "RUN-SHARED",
        {"run": {"id": "RUN-SHARED", "workflow": "A"}, "patches": [], "violations": []},
        tenant_id="tenant-a",
    )
    put_run(
        "RUN-SHARED",
        {"run": {"id": "RUN-SHARED", "workflow": "B"}, "patches": [], "violations": []},
        tenant_id="tenant-b",
    )

    assert get_run("RUN-SHARED", tenant_id="tenant-a")["run"]["workflow"] == "A"
    assert get_run("RUN-SHARED", tenant_id="tenant-b")["run"]["workflow"] == "B"


def test_same_workflow_id_can_exist_per_tenant(tmp_path):
    from api.db import session_scope
    from api.models import WorkflowRecord
    from api.store import get_workflow

    _configure_db(tmp_path)
    with session_scope() as session:
        session.add(WorkflowRecord(workflow_id="WF-SHARED", tenant_id="tenant-a", name="A"))
        session.add(WorkflowRecord(workflow_id="WF-SHARED", tenant_id="tenant-b", name="B"))
        session.commit()

    assert get_workflow("WF-SHARED", tenant_id="tenant-a")["name"] == "A"
    assert get_workflow("WF-SHARED", tenant_id="tenant-b")["name"] == "B"


def test_completed_run_persists_violation_recurrence_fields(tmp_path):
    from sqlmodel import select

    from api.db import configure_database, init_db, session_scope
    from api.models import ViolationRecord
    from api.store import create_workflow, put_run

    db_url = _configure_db(tmp_path)
    workflow = create_workflow(
        {
            "name": "RecurringWorkflow",
            "declared_topology": {},
            "agents": [{"name": "ReporterAgent"}],
            "tools": [],
            "contracts": [],
        }
    )
    put_run(
        "RUN-REC-1",
        {
            "run": {"id": "RUN-REC-1", "workflow": "RecurringWorkflow"},
            "patches": [],
            "violations": [
                {
                    "contract_type": "evidence",
                    "severity": "HIGH",
                    "rule": "verified_sources_count must be > 0",
                    "failed_agent": "ReporterAgent",
                    "failed_step": 5,
                }
            ],
            "report": {"approval": {"status": "PENDING_OPERATOR"}},
        },
        workflow_id=workflow["workflow_id"],
        status="completed",
    )

    configure_database(db_url)
    init_db()

    with session_scope() as session:
        rows = session.exec(
            select(ViolationRecord).where(ViolationRecord.run_id == "RUN-REC-1")
        ).all()

    assert len(rows) == 1
    assert rows[0].workflow_id == workflow["workflow_id"]
    assert rows[0].recurrence_key == (
        "evidence|ReporterAgent|verified_sources_count must be > 0"
    )


def test_run_persistence_survives_graph_failure_after_sql_commit(tmp_path, monkeypatch):
    from api.store import get_run, put_run

    _configure_db(tmp_path)

    def fail_graph_call(**_kwargs):
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr("api.store.persist_run_violations", fail_graph_call)

    put_run(
        "RUN-GRAPH-FAIL",
        {
            "run": {"id": "RUN-GRAPH-FAIL", "workflow": "GraphFailureWorkflow"},
            "patches": [],
            "violations": [
                {
                    "contract_type": "routing",
                    "severity": "MED",
                    "rule": "Reporter handoff must be gated",
                    "failed_agent": "GroupChatManager",
                    "failed_step": 10,
                }
            ],
        },
        workflow_id="WF-GRAPH-FAIL",
        status="completed",
    )

    assert get_run("RUN-GRAPH-FAIL")["status"] == "completed"
