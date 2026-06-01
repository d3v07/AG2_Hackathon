"""Unit tests for TaskSpec and RunCreate Pydantic schemas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas import RunCreate, TaskSpec


def test_valid_task_spec_parses() -> None:
    spec = TaskSpec(task="research reliability", research_question="What makes systems reliable?")
    assert spec.task == "research reliability"
    assert spec.research_question == "What makes systems reliable?"
    assert spec.mode == "live"


def test_missing_task_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TaskSpec(research_question="What makes systems reliable?")  # type: ignore[call-arg]
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("task",) for e in errors)


def test_missing_research_question_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TaskSpec(task="research reliability")  # type: ignore[call-arg]
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("research_question",) for e in errors)


def test_empty_task_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TaskSpec(task="", research_question="What makes systems reliable?")
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("task",) for e in errors)


def test_empty_research_question_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TaskSpec(task="research reliability", research_question="")
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("research_question",) for e in errors)


def test_unknown_mode_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TaskSpec(task="research reliability", research_question="Why?", mode="invalid")  # type: ignore[arg-type]
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("mode",) for e in errors)


def test_default_mode_is_live() -> None:
    spec = TaskSpec(task="research reliability", research_question="Why?")
    assert spec.mode == "live"


def test_run_create_with_valid_task_spec_parses() -> None:
    run = RunCreate(
        workflow_id="wf-123",
        task_spec={"task": "research reliability", "research_question": "Why?"},
    )
    assert isinstance(run.task_spec, TaskSpec)
    assert run.task_spec.task == "research reliability"
    assert run.task_spec.mode == "live"
    assert run.raw_trace is None


def test_run_create_rejects_both_raw_trace_and_task_spec() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RunCreate(
            workflow_id="wf-123",
            raw_trace={"events": []},
            task_spec={"task": "t", "research_question": "q"},
        )
    assert "exactly one" in str(exc_info.value).lower()


def test_run_create_rejects_neither_raw_trace_nor_task_spec() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RunCreate(workflow_id="wf-123")
    assert "exactly one" in str(exc_info.value).lower()
