import asyncio
import pytest

from shared.models import ContextSnapshot, RunTrace
from zone_b.agents.contract_checker import CONTRACTS
from zone_b.agents.trace_collector import run_trace_collector


REQUIRED_SCHEMA_KEYS = {"summary", "claims", "citations", "risks", "next_steps"}


def _schema_contract() -> dict:
    return next(c for c in CONTRACTS if c["type"] == "schema")


def _snapshot(final_output) -> ContextSnapshot:
    return ContextSnapshot(
        retrieved_sources=["src"],
        verified_sources_count=1,
        tool_events=[],
        approval_status="approved",
        failed_agent=None,
        failed_step=None,
        final_output=final_output,
    )


def _trace() -> RunTrace:
    return RunTrace(run_id="r", workflow_name="w", events=[], final_output=None)


@pytest.mark.parametrize("missing_key", sorted(REQUIRED_SCHEMA_KEYS))
def test_schema_contract_fails_when_any_required_key_is_missing(missing_key):
    final_output = {
        "summary": "done",
        "claims": [],
        "citations": [],
        "risks": [],
        "next_steps": [],
    }
    final_output.pop(missing_key)

    assert _schema_contract()["check"](_trace(), _snapshot(final_output)) is False


def test_schema_contract_passes_on_fixture_trace(sample_trace_raw):
    collected = asyncio.run(run_trace_collector(sample_trace_raw))

    assert (
        _schema_contract()["check"](
            collected["run_trace"],
            collected["context_snapshot"],
        )
        is True
    )
