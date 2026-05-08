"""Pydantic request/response schemas for the API layer."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class WorkflowCreate(BaseModel):
    name: str
    declared_topology: dict[str, Any] = Field(default_factory=dict)
    agents: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    contracts: list[dict[str, Any]] = Field(default_factory=list)
    contracts_yaml: str | None = None
    owner: str = ""


class TaskSpec(BaseModel):
    task: str = Field(..., min_length=1)
    research_question: str = Field(..., min_length=1)
    mode: Literal["stub", "live"] = "stub"


class RunCreate(BaseModel):
    workflow_id: str
    raw_trace: dict[str, Any] | None = None
    task_spec: TaskSpec | None = None

    @model_validator(mode="after")
    def exactly_one_input(self) -> "RunCreate":
        if (self.raw_trace is None) == (self.task_spec is None):
            raise ValueError("provide exactly one of raw_trace or task_spec")
        return self


class ApprovalBody(BaseModel):
    decision: str
    operator: str = "j.kowalski"
    comments: str = ""


class ApiKeyCreate(BaseModel):
    tenant_id: str | None = None
    name: str = ""
