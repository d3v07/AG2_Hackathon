import asyncio
import json
from shared.models import RunTrace, TraceEvent, ToolEvent, ContextSnapshot


def _parse_tool_events(raw_list: list) -> list[ToolEvent]:
    """Parse raw tool event dicts into ToolEvent dataclasses."""
    events = []
    for t in raw_list:
        events.append(ToolEvent(
            tool_name=t.get("tool_name", ""),
            input=t.get("input"),
            output=t.get("output"),
            status=t.get("status", "success"),
            evidence_id=t.get("evidence_id", ""),
            timestamp=t.get("timestamp", 0.0),
        ))
    return events


def _parse_trace_events(raw_events: list) -> list[TraceEvent]:
    """Parse raw event dicts into TraceEvent dataclasses."""
    events = []
    for e in raw_events:
        cd = e.get("context_delta", {})
        # normalise tool_events inside context_delta from dicts to ToolEvent
        if "tool_events" in cd and isinstance(cd["tool_events"], list):
            cd = dict(cd)
            cd["tool_events"] = _parse_tool_events(cd["tool_events"])
        events.append(TraceEvent(
            step=e["step"],
            agent=e["agent"],
            type=e["type"],
            content=e["content"],
            tool_call_id=e.get("tool_call_id"),
            context_delta=cd,
            handoff_to=e.get("handoff_to"),
            timestamp=e.get("timestamp", 0.0),
        ))
    return events


def _build_context_snapshot(events: list[TraceEvent]) -> ContextSnapshot:
    """Fold all context_delta updates left-to-right to build final ContextSnapshot."""
    state: dict = {
        "retrieved_sources": [],
        "verified_sources_count": 0,
        "tool_events": [],
        "approval_status": "pending",
        "failed_agent": None,
        "failed_step": None,
        "final_output": None,
    }
    for e in events:
        for key, val in e.context_delta.items():
            if key == "tool_events" and isinstance(val, list):
                state["tool_events"].extend(val)
            else:
                state[key] = val

    return ContextSnapshot(
        retrieved_sources=state.get("retrieved_sources", []),
        verified_sources_count=state.get("verified_sources_count", 0),
        tool_events=state.get("tool_events", []),
        approval_status=state.get("approval_status", "pending"),
        failed_agent=state.get("failed_agent"),
        failed_step=state.get("failed_step"),
        final_output=state.get("final_output"),
    )


async def run_trace_collector(raw: dict) -> dict:
    """Parse raw JSON trace into normalised RunTrace and ContextSnapshot."""
    events = _parse_trace_events(raw.get("events", []))
    run_trace = RunTrace(
        run_id=raw["run_id"],
        workflow_name=raw["workflow_name"],
        events=events,
        final_output=raw.get("final_output"),
    )
    context_snapshot = _build_context_snapshot(events)
    handoff_path = [e.agent for e in events]
    tool_events = [
        te
        for e in events
        for te in (e.context_delta.get("tool_events") or [])
        if isinstance(te, ToolEvent)
    ]
    summary = (
        f"{run_trace.run_id}: {len(events)} events, "
        f"{len(tool_events)} tool call(s), "
        f"handoff path length {len(handoff_path)}"
    )
    return {
        "run_trace": run_trace,
        "context_snapshot": context_snapshot,
        "handoff_path": handoff_path,
        "tool_events": tool_events,
        "summary": summary,
        "spans": raw.get("spans") or [],
    }


if __name__ == "__main__":
    import json
    from pathlib import Path

    raw = json.loads(Path("zone_b/fixtures/sample_trace.json").read_text())
    result = asyncio.run(run_trace_collector(raw))
    print("Summary:", result["summary"])
    print("Handoff path:", result["handoff_path"])
    print("Context snapshot:")
    snap = result["context_snapshot"]
    print(f"  verified_sources_count : {snap.verified_sources_count}")
    print(f"  approval_status        : {snap.approval_status}")
    print(f"  tool_events            : {len(snap.tool_events)}")
