import json
import pytest
from pathlib import Path
from shared.models import (
    RunTrace, TraceEvent, ContextSnapshot
)


@pytest.fixture
def sample_trace_raw() -> dict:
    return json.loads(Path("zone_b/fixtures/sample_trace.json").read_text())


@pytest.fixture
def clean_trace_raw() -> dict:
    """A fully passing trace — no contract violations."""
    return {
        "run_id": "run_clean",
        "workflow_name": "LiteratureReviewAssistant",
        "events": [
            {
                "step": 1, "agent": "ResearcherAgent", "type": "agent_turn",
                "content": "Found 3 sources.",
                "tool_call_id": "tc_001",
                "context_delta": {
                    "retrieved_sources": ["src1", "src2", "src3"],
                    "tool_events": [
                        {"tool_name": "tavily_search", "input": "q", "output": "r",
                         "status": "success", "evidence_id": "ev_001", "timestamp": 0.1}
                    ]
                },
                "handoff_to": "CriticAgent", "timestamp": 0.1
            },
            {
                "step": 2, "agent": "CriticAgent", "type": "agent_turn",
                "content": "Sources look solid.", "tool_call_id": None,
                "context_delta": {}, "handoff_to": "VerifierAgent", "timestamp": 0.5
            },
            {
                "step": 3, "agent": "VerifierAgent", "type": "agent_turn",
                "content": "Verified all claims.",
                "tool_call_id": "tc_002",
                "context_delta": {
                    "verified_sources_count": 3,
                    "approval_status": "approved",
                    "tool_events": [
                        {"tool_name": "tavily_search", "input": "q", "output": "r",
                         "status": "success", "evidence_id": "ev_002", "timestamp": 1.0}
                    ],
                },
                "handoff_to": "ReporterAgent", "timestamp": 1.0
            },
            {
                "step": 4, "agent": "ReporterAgent", "type": "agent_turn",
                "content": "Final memo written.", "tool_call_id": None,
                "context_delta": {
                    "final_output": {
                        "summary": "MAS improve reliability.",
                        "claims": ["c1"], "citations": ["r1"], "risks": [], "next_steps": []
                    }
                },
                "handoff_to": "HumanGateAgent", "timestamp": 2.0
            },
            {
                "step": 5, "agent": "HumanGateAgent", "type": "agent_turn",
                "content": "Approved.", "tool_call_id": None,
                "context_delta": {"approval_status": "approved"},
                "handoff_to": "ActionAgent", "timestamp": 2.2
            },
            {
                "step": 6, "agent": "ActionAgent", "type": "agent_turn",
                "content": "Report saved.", "tool_call_id": None,
                "context_delta": {}, "handoff_to": None, "timestamp": 2.5
            },
        ],
        "final_output": {"summary": "MAS improve reliability."}
    }


@pytest.fixture
def minimal_run_trace() -> RunTrace:
    return RunTrace(
        run_id="run_test",
        workflow_name="TestWorkflow",
        events=[
            TraceEvent(
                step=1, agent="AgentA", type="agent_turn",
                content="Hello", tool_call_id="tc_1",
                context_delta={"verified_sources_count": 2},
                handoff_to="AgentB", timestamp=0.1
            ),
            TraceEvent(
                step=2, agent="VerifierAgent", type="agent_turn",
                content="Verified", tool_call_id=None,
                context_delta={"verified_sources_count": 0},
                handoff_to=None, timestamp=0.2
            ),
        ],
        final_output=None
    )


@pytest.fixture
def passing_context_snapshot() -> ContextSnapshot:
    return ContextSnapshot(
        retrieved_sources=["src1", "src2"],
        verified_sources_count=3,
        tool_events=[],
        approval_status="approved",
        failed_agent=None,
        failed_step=None,
        final_output=None,
    )


@pytest.fixture
def failing_context_snapshot() -> ContextSnapshot:
    return ContextSnapshot(
        retrieved_sources=[],
        verified_sources_count=0,
        tool_events=[],
        approval_status="pending",
        failed_agent=None,
        failed_step=None,
        final_output=None,
    )
