import asyncio

from shared.models import ContextSnapshot, RunTrace, ToolEvent, TraceEvent
from zone_b.agents.contract_checker import CONTRACTS
from zone_b.agents.trace_collector import run_trace_collector


def _routing_contract() -> dict:
    return next(c for c in CONTRACTS if c["type"] == "routing")


def _event(
    step: int,
    agent: str,
    *,
    tool_call_id: str | None = None,
    context_delta: dict | None = None,
    handoff_to: str | None = None,
) -> TraceEvent:
    return TraceEvent(
        step=step,
        agent=agent,
        type="agent_turn",
        content="",
        tool_call_id=tool_call_id,
        context_delta=context_delta or {},
        handoff_to=handoff_to,
        timestamp=float(step),
    )


def test_routing_contract_fails_on_fixture_trace(sample_trace_raw):
    collected = asyncio.run(run_trace_collector(sample_trace_raw))

    assert (
        _routing_contract()["check"](
            collected["run_trace"],
            collected["context_snapshot"],
        )
        is False
    )


def test_routing_contract_passes_on_clean_ordered_trace():
    verifier_tool = ToolEvent(
        tool_name="tavily_search",
        input="q",
        output="r",
        status="success",
        evidence_id="ev_002",
        timestamp=2.5,
    )
    trace = RunTrace(
        run_id="r",
        workflow_name="w",
        events=[
            _event(1, "ResearcherAgent", handoff_to="CriticAgent"),
            _event(2, "CriticAgent", handoff_to="VerifierAgent"),
            _event(
                3,
                "VerifierAgent",
                tool_call_id="tc_002",
                context_delta={"tool_events": [verifier_tool]},
                handoff_to="ReporterAgent",
            ),
            _event(4, "ReporterAgent", handoff_to="HumanGateAgent"),
            _event(
                5,
                "HumanGateAgent",
                context_delta={"approval_status": "approved"},
                handoff_to="ActionAgent",
            ),
            _event(6, "ActionAgent"),
        ],
        final_output={"summary": "done"},
    )
    snap = ContextSnapshot(
        retrieved_sources=["src"],
        verified_sources_count=1,
        tool_events=[verifier_tool],
        approval_status="approved",
        failed_agent=None,
        failed_step=None,
        final_output={"summary": "done"},
    )

    assert _routing_contract()["check"](trace, snap) is True


def test_routing_contract_requires_successful_verifier_tool_event():
    trace = RunTrace(
        run_id="r",
        workflow_name="w",
        events=[
            _event(1, "VerifierAgent", tool_call_id="tc_002", handoff_to="ReporterAgent"),
            _event(2, "ReporterAgent", handoff_to="HumanGateAgent"),
            _event(3, "HumanGateAgent", handoff_to="ActionAgent"),
            _event(4, "ActionAgent"),
        ],
        final_output={"summary": "done"},
    )
    snap = ContextSnapshot(
        retrieved_sources=["src"],
        verified_sources_count=1,
        tool_events=[],
        approval_status="approved",
        failed_agent=None,
        failed_step=None,
        final_output={"summary": "done"},
    )

    assert _routing_contract()["check"](trace, snap) is False
