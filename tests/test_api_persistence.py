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
    assert "RUN-041" in list_runs()

    configure_database(db_url)
    init_db()

    restarted = get_run("RUN-041")
    assert restarted is not None
    assert restarted["run"]["id"] == "RUN-041"
    assert len(restarted["patches"]) == 4


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
