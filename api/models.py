"""SQLModel persistence records for Concord API state."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class WorkflowRecord(SQLModel, table=True):
    __tablename__ = "workflows"

    workflow_id: str = Field(primary_key=True)
    tenant_id: str = Field(default="local", primary_key=True, index=True)
    name: str = Field(index=True)
    owner: str = ""
    declared_topology_json: str = "{}"
    agents_json: str = "[]"
    tools_json: str = "[]"
    contracts_json: str = "[]"
    created_at: str = Field(default_factory=_utc_now)


class RunRecord(SQLModel, table=True):
    __tablename__ = "runs"

    run_id: str = Field(primary_key=True)
    tenant_id: str = Field(default="local", primary_key=True, index=True)
    workflow_id: str = Field(default="", index=True)
    status: str = Field(default="queued", index=True)
    raw_trace_json: str = ""
    task_spec_json: str = ""
    report_json: str = ""
    daytona_seconds: float = 0.0
    llm_tokens: int = 0
    llm_cost_usd: float = 0.0
    daytona_cost_usd: float = 0.0
    error: str = ""
    status_history_json: str = "[]"
    created_at: str = Field(default_factory=_utc_now)
    updated_at: str = Field(default_factory=_utc_now)


class ViolationRecord(SQLModel, table=True):
    __tablename__ = "violations"

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="local", index=True)
    run_id: str = Field(index=True)
    contract_type: str = Field(default="", index=True)
    severity: str = ""
    failed_agent: str = ""
    failed_step: int = -1
    payload_json: str = "{}"


class PatchRecord(SQLModel, table=True):
    __tablename__ = "patches"

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="local", index=True)
    run_id: str = Field(index=True)
    violation_id: str = ""
    primitive: str = ""
    target: str = ""
    payload_json: str = "{}"


class TestRecord(SQLModel, table=True):
    __tablename__ = "tests"

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="local", index=True)
    run_id: str = Field(index=True)
    status: str = ""
    payload_json: str = "{}"
