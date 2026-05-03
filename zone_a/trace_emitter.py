import json
import dataclasses
from pathlib import Path
from shared.models import RunTrace, ContextSnapshot, TraceEvent

_OUTPUT_PATH = Path("zone_b/fixtures/sample_trace.json")


def emit_trace(context: ContextSnapshot, events: list[TraceEvent], run_id: str) -> None:
    trace = RunTrace(
        run_id=run_id,
        workflow_name="LiteratureReviewAssistant",
        events=events,
        final_output=context.final_output,
    )
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps(dataclasses.asdict(trace), indent=2))


if __name__ == "__main__":
    import time
    from shared.models import ToolEvent

    sample_events = [
        TraceEvent(
            step=3,
            agent="VerifierAgent",
            type="agent_turn",
            content="Verification complete",
            tool_call_id=None,
            context_delta={"verified_sources_count": 0},
            handoff_to="ReporterAgent",
            timestamp=time.time(),
        ),
        TraceEvent(
            step=4,
            agent="ReporterAgent",
            type="agent_turn",
            content="Report generated",
            tool_call_id=None,
            context_delta={"final_output": {"summary": "Test"}},
            handoff_to="ActionAgent",
            timestamp=time.time(),
        ),
        TraceEvent(
            step=5,
            agent="ActionAgent",
            type="agent_turn",
            content="Action taken",
            tool_call_id=None,
            context_delta={},
            handoff_to=None,
            timestamp=time.time(),
        ),
    ]
    sample_context = ContextSnapshot(
        retrieved_sources=[],
        verified_sources_count=0,
        tool_events=[],
        approval_status="pending",
        failed_agent=None,
        failed_step=None,
        final_output={"summary": "Test"},
    )
    emit_trace(sample_context, sample_events, run_id="test-run-001")
    print(f"Trace written to {_OUTPUT_PATH}")
