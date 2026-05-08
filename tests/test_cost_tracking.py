"""Cost tracking tests for sandbox execution and persisted API runs."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import select


def _configure_db(tmp_path):
    from api.db import configure_database, init_db

    db_url = f"sqlite:///{tmp_path / 'costs.db'}"
    configure_database(db_url)
    init_db()
    return db_url


def test_run_record_declares_cost_fields():
    from api.models import RunRecord

    for field in (
        "daytona_seconds",
        "llm_tokens",
        "llm_cost_usd",
        "daytona_cost_usd",
    ):
        assert field in RunRecord.model_fields


def test_store_persists_cost_columns_and_get_run_payload(tmp_path):
    from api.db import configure_database, init_db, session_scope
    from api.models import RunRecord
    from api.store import get_run, put_run

    db_url = _configure_db(tmp_path)
    put_run(
        "RUN-COST",
        {
            "run": {"id": "RUN-COST", "workflow": "cost-workflow"},
            "patches": [],
            "violations": [],
            "cost": {
                "daytona_seconds": 1.25,
                "llm_tokens": 32,
                "llm_cost_usd": 0.00016,
                "daytona_cost_usd": 0.00025,
            },
            "report": {"approval": {"status": "PENDING_OPERATOR"}},
        },
        status="completed",
    )

    with session_scope() as session:
        record = session.exec(
            select(RunRecord).where(
                RunRecord.run_id == "RUN-COST",
                RunRecord.tenant_id == "local",
            )
        ).one()
        assert record.daytona_seconds == 1.25
        assert record.llm_tokens == 32
        assert record.llm_cost_usd == 0.00016
        assert record.daytona_cost_usd == 0.00025

    configure_database(db_url)
    init_db()

    assert get_run("RUN-COST")["cost"] == {
        "daytona_seconds": 1.25,
        "llm_tokens": 32,
        "llm_cost_usd": 0.00016,
        "daytona_cost_usd": 0.00025,
    }


def test_get_run_endpoint_returns_cost_block(tmp_path):
    from api.index import app
    from api.store import put_run

    _configure_db(tmp_path)
    put_run(
        "RUN-COST-API",
        {
            "run": {"id": "RUN-COST-API", "workflow": "cost-workflow"},
            "patches": [],
            "violations": [],
            "cost": {
                "daytona_seconds": 2.5,
                "llm_tokens": 0,
                "llm_cost_usd": 0,
                "daytona_cost_usd": 0.0005,
            },
            "report": {"approval": {"status": "PENDING_OPERATOR"}},
        },
        status="completed",
    )

    response = TestClient(app).get("/api/runs/RUN-COST-API")

    assert response.status_code == 200
    assert response.json()["cost"] == {
        "daytona_seconds": 2.5,
        "llm_tokens": 0,
        "llm_cost_usd": 0,
        "daytona_cost_usd": 0.0005,
    }
