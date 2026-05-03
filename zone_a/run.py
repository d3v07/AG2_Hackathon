"""Zone A entry point — runs the Literature Review Assistant pipeline.

Chains all 5 agents sequentially, builds TraceEvent objects from each
agent's return dict, then calls trace_emitter to write sample_trace.json
for Zone B to consume.

Intentional failures baked in:
  - VerifierAgent: tool_call_id=None, verified_sources_count=0
  - ReporterAgent: runs despite unverified sources
  - ActionAgent: runs without approval_status=approved
"""
import json
import time
from pathlib import Path
from shared.models import TraceEvent, ContextSnapshot, ToolEvent
from zone_a.agents.researcher import run_researcher
from zone_a.agents.critic import run_critic
from zone_a.agents.verifier import run_verifier
from zone_a.agents.reporter import run_reporter
from zone_a.agents.action_agent import run_action_agent
from zone_a.agents.human_gate import run_human_gate
from zone_a.trace_emitter import emit_trace


def _to_trace_event(d: dict) -> TraceEvent:
    cd = dict(d.get("context_delta", {}))
    if "tool_events" in cd and isinstance(cd["tool_events"], list):
        cd["tool_events"] = [
            ToolEvent(**te) if isinstance(te, dict) else te
            for te in cd["tool_events"]
        ]
    return TraceEvent(
        step=d["step"],
        agent=d["agent"],
        type=d["type"],
        content=d["content"],
        tool_call_id=d.get("tool_call_id"),
        context_delta=cd,
        handoff_to=d.get("handoff_to"),
        timestamp=d.get("timestamp", time.time()),
    )


def run() -> None:
    fixture = json.loads(Path("zone_a/fixtures/task.json").read_text())
    task = fixture["task"]
    research_question = fixture["research_question"]
    run_id = fixture.get("run_id", "run_001")

    print("=" * 55)
    print("  ZONE A — Literature Review Assistant")
    print("=" * 55)

    print("\n[1/5] ResearcherAgent")
    r1 = run_researcher(task, research_question)
    sources = r1["context_delta"]["retrieved_sources"]
    print(f"      sources found: {len(sources)}")

    print("\n[2/5] CriticAgent")
    r2 = run_critic(sources, task)
    print("      critique complete")

    print("\n[3/5] VerifierAgent (intentionally broken)")
    r3 = run_verifier(sources, [])
    print(f"      verified_sources_count: {r3['context_delta']['verified_sources_count']}")
    print(f"      tool_call_id: {r3['tool_call_id']}")

    print("\n[4/5] ReporterAgent (runs despite unverified sources)")
    r4 = run_reporter(r3["context_delta"]["verified_sources_count"], sources, [])
    print("      report generated")

    print("\n[HumanGate] (intentionally stays pending)")
    gate = run_human_gate(r4["context_delta"]["final_output"])
    approval_status = gate["approval_status"]
    print(f"      approval_status: {approval_status}")

    print("\n[5/5] ActionAgent (runs without approval)")
    r5 = run_action_agent(r4["context_delta"]["final_output"], approval_status)
    print("      action taken")

    events = [_to_trace_event(r) for r in [r1, r2, r3, r4, r5]]
    context = ContextSnapshot(
        retrieved_sources=sources,
        verified_sources_count=0,
        tool_events=[],
        approval_status=approval_status,
        failed_agent=None,
        failed_step=None,
        final_output=r4["context_delta"]["final_output"],
    )

    emit_trace(context, events, run_id=run_id)
    print(f"\n  Trace written → zone_b/fixtures/sample_trace.json")
    print("=" * 55)


if __name__ == "__main__":
    run()
