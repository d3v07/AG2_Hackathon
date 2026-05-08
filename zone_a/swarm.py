"""Zone A AG2 Swarm — RoundRobinPattern with OnContextCondition handoffs.

Replaces the sequential function-call pipeline in zone_a/run.py with a true
AG2 swarm where contract violations are enforced at the framework level:

- VerifierAgent's OnContextCondition gates progression to ReporterAgent on
  `sources_verified` — if False (C1: no verified sources, or C2: missing
  tool_call_id) the swarm terminates instead of continuing.
- HumanGateAgent's OnContextCondition gates progression to ActionAgent on
  `approval_granted` — if False (C3: action without approval) the swarm
  terminates.
- A RegexGuardrail on VerifierAgent output also terminates if no `tc_*`
  identifier is present, providing a second-line C2 enforcement.

The legacy zone_a/run.py is preserved for fixture regeneration and
backward-compat with the existing test suite. This module is a new entry
point invoked via `run_all.py --swarm`.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Literal

from shared.logging import get_logger

from autogen import ConversableAgent
from autogen.agentchat.group import (
    AgentTarget,
    ContextVariables,
    OnContextCondition,
    StringContextCondition,
    TerminateTarget,
)
from autogen.agentchat.group.guardrails import RegexGuardrail
from autogen.agentchat.group.multi_agent_chat import a_initiate_group_chat
from autogen.agentchat.group.patterns import RoundRobinPattern

from shared.models import ContextSnapshot, ToolEvent, TraceEvent
from zone_a.config import get_llm_config
from zone_a.swarm_tools import (
    record_action,
    record_approval,
    record_critique,
    record_report,
    record_research,
    record_verification,
)
from zone_a.trace_emitter import emit_trace


_RESEARCHER_SYSTEM = """\
You are ResearcherAgent in a Literature Review Assistant swarm.

The user message contains a task and research question. Search-results context
will be provided in the conversation. Your job: call the `record_research`
tool with the structured sources and a tool_call_id like "tc_001". Always
include a tool_call_id starting with "tc_". Return at most 3 sources.
"""

_CRITIC_SYSTEM = """\
You are CriticAgent. Read the retrieved sources and produce critique notes
and risk flags. ALWAYS call the `record_critique` tool with at least 2
critique_notes and 1 risk_flag.
"""

_VERIFIER_SYSTEM = """\
You are VerifierAgent — the C1 + C2 contract gate.

Read the retrieved sources and call the `record_verification` tool with:
  - verified_sources_count: how many sources you could fully verify (an int)
  - tool_call_id: a string starting with "tc_" if you ran a verification tool,
    otherwise pass null
  - narrative: one-sentence verification outcome

If you cannot verify any source, pass verified_sources_count=0 and
tool_call_id=null — the swarm will terminate at this point.
"""

_REPORTER_SYSTEM = """\
You are ReporterAgent. You only run if sources were verified. Produce the
final structured memo by calling the `record_report` tool with summary,
claims, citations, risks, and next_steps fields.
"""

_HUMAN_GATE_SYSTEM = """\
You are HumanGateAgent — the C3 approval gate.

Read the report and decide whether to approve the action. Call
`record_approval` with approval_granted=true (and one-sentence comments) only
if the report is sound. Otherwise approval_granted=false. The swarm only
proceeds to ActionAgent if you approve.
"""

_ACTION_SYSTEM = """\
You are ActionAgent. You only run if HumanGate approved. Call `record_action`
with one sentence describing the concrete side-effect you took.
"""


def _initial_context() -> ContextVariables:
    return ContextVariables(
        data={
            "retrieved_sources": [],
            "researcher_tool_call_id": "",
            "researcher_summary": "",
            "critique_notes": [],
            "risk_flags": [],
            "verified_sources_count": 0,
            "verifier_tool_call_id": "",
            "verifier_narrative": "",
            "sources_verified": False,
            "final_output": None,
            "approval_granted": False,
            "approval_status": "pending",
            "approval_comments": "",
            "action_taken": "",
        }
    )


def build_swarm(
    llm_config: dict[str, Any] | None = None,
    interactive: bool = False,
) -> tuple[list[ConversableAgent], ContextVariables]:
    """Construct the 6-agent Zone A swarm with handoffs and guardrails.

    Returns the agent list (in round-robin order) and the initial
    ContextVariables. No LLM is called at construction time, so this is
    safe to use in tests with a fake llm_config.
    """
    if llm_config is None:
        llm_config = get_llm_config()

    ctx = _initial_context()

    researcher = ConversableAgent(
        name="ResearcherAgent",
        system_message=_RESEARCHER_SYSTEM,
        llm_config=llm_config,
        human_input_mode="NEVER",
        code_execution_config=False,
    )
    critic = ConversableAgent(
        name="CriticAgent",
        system_message=_CRITIC_SYSTEM,
        llm_config=llm_config,
        human_input_mode="NEVER",
        code_execution_config=False,
    )
    verifier = ConversableAgent(
        name="VerifierAgent",
        system_message=_VERIFIER_SYSTEM,
        llm_config=llm_config,
        human_input_mode="NEVER",
        code_execution_config=False,
    )
    reporter = ConversableAgent(
        name="ReporterAgent",
        system_message=_REPORTER_SYSTEM,
        llm_config=llm_config,
        human_input_mode="NEVER",
        code_execution_config=False,
    )
    human_gate = ConversableAgent(
        name="HumanGateAgent",
        system_message=_HUMAN_GATE_SYSTEM,
        llm_config=llm_config,
        human_input_mode="ALWAYS" if interactive else "NEVER",
        code_execution_config=False,
    )
    action = ConversableAgent(
        name="ActionAgent",
        system_message=_ACTION_SYSTEM,
        llm_config=llm_config,
        human_input_mode="NEVER",
        code_execution_config=False,
    )

    researcher.register_for_llm(
        name="record_research", description="Record retrieved sources + tool_call_id."
    )(record_research)
    critic.register_for_llm(
        name="record_critique", description="Record critique notes and risks."
    )(record_critique)
    verifier.register_for_llm(
        name="record_verification",
        description="Record verification result. C1+C2 gate.",
    )(record_verification)
    reporter.register_for_llm(
        name="record_report", description="Record final structured memo."
    )(record_report)
    human_gate.register_for_llm(
        name="record_approval", description="Record human approval. C3 gate."
    )(record_approval)
    action.register_for_llm(
        name="record_action", description="Record side-effect taken."
    )(record_action)

    verifier.register_handoffs(
        [
            OnContextCondition(
                target=AgentTarget(agent=reporter),
                condition=StringContextCondition(variable_name="sources_verified"),
            ),
            OnContextCondition(target=TerminateTarget(), condition=None),
        ]
    )

    human_gate.register_handoffs(
        [
            OnContextCondition(
                target=AgentTarget(agent=action),
                condition=StringContextCondition(variable_name="approval_granted"),
            ),
            OnContextCondition(target=TerminateTarget(), condition=None),
        ]
    )

    # Secondary C2 enforcement: fires only if VerifierAgent narrates a missing
    # tool_call_id in plain text. Primary C2 enforcement is the OnContextCondition
    # catch-all above (sources_verified=False when verifier_tool_call_id is empty).
    verifier.register_output_guardrail(
        RegexGuardrail(
            name="C2_missing_tool_call_id",
            condition=r"tool_call_id\s*[:=]\s*(null|None|\"\"|'')",
            target=TerminateTarget(),
            activation_message=(
                "C2 violation: VerifierAgent reply indicates no tool_call_id. "
                "Terminating swarm to prevent unverified handoff."
            ),
        )
    )

    return [researcher, critic, verifier, reporter, human_gate, action], ctx


_TAVILY_FALLBACK_PATH = Path(__file__).parent / "fixtures" / "tavily_fallback.json"


def _load_tavily_fallback() -> list[dict[str, Any]]:
    """Read the committed offline fallback fixture (3 sources)."""
    return json.loads(_TAVILY_FALLBACK_PATH.read_text()).get("results", [])


def _build_initial_message(task: str, research_question: str) -> str:
    """Pre-fetch Tavily results so ResearcherAgent has context.

    All failure paths (missing key, network error, rate limit, bad response
    shape) fall back to the committed offline fixture. Every path emits a
    structured log line so failures are debuggable in production. Tavily
    stays the ONLY search source — the fallback is offline data, not another
    vendor.
    """
    logger = get_logger("zone_a.swarm")
    tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not tavily_key:
        logger.warning(
            "zone_a.tavily.missing_key",
            extra={"using_fallback": True, "reason": "no TAVILY_API_KEY env var"},
        )
        results = _load_tavily_fallback()
        return _render_initial_message(task, research_question, results, source="fallback:no_key")

    start = time.monotonic()
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=tavily_key)
        raw = client.search(
            query=research_question, max_results=3, search_depth="basic"
        )
        if not isinstance(raw, dict) or not isinstance(raw.get("results"), list):
            logger.warning(
                "zone_a.tavily.bad_response_shape",
                extra={
                    "using_fallback": True,
                    "latency_ms": int((time.monotonic() - start) * 1000),
                },
            )
            return _render_initial_message(
                task, research_question, _load_tavily_fallback(), source="fallback:bad_shape"
            )
        results = raw["results"]
        logger.info(
            "zone_a.tavily.search",
            extra={
                "query": research_question,
                "status": "success",
                "source_count": len(results),
                "latency_ms": int((time.monotonic() - start) * 1000),
            },
        )
        return _render_initial_message(task, research_question, results, source="tavily")
    except Exception as exc:
        logger.warning(
            "zone_a.tavily.error",
            extra={
                "using_fallback": True,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "latency_ms": int((time.monotonic() - start) * 1000),
            },
        )
        return _render_initial_message(
            task,
            research_question,
            _load_tavily_fallback(),
            source=f"fallback:{type(exc).__name__}",
        )


def _render_initial_message(
    task: str, research_question: str, results: list[dict[str, Any]], source: str
) -> str:
    serialized = json.dumps(results, indent=2)
    return (
        f"Task: {task}\n\nResearch question: {research_question}\n\n"
        f"Search results (source={source}):\n{serialized}\n\n"
        "Call `record_research` to record sources and tool_call_id."
    )


def _chat_history_to_trace_events(
    chat_history: list[dict[str, Any]],
    final_ctx: ContextVariables,
) -> list[TraceEvent]:
    """Walk the swarm chat history and produce TraceEvent objects for Zone B."""
    agent_to_step = {
        "ResearcherAgent": 1,
        "CriticAgent": 2,
        "VerifierAgent": 3,
        "ReporterAgent": 4,
        "HumanGateAgent": 5,
        "ActionAgent": 6,
    }
    seen: set[str] = set()
    events: list[TraceEvent] = []
    now = 0.0  # fixed timestamp keeps stub mode fully deterministic across runs

    for msg in chat_history:
        name = msg.get("name") or ""
        if name not in agent_to_step or name in seen:
            continue
        seen.add(name)

        content = msg.get("content") or ""
        tool_call_id: str | None = None
        context_delta: dict[str, Any] = {}

        if name == "ResearcherAgent":
            tool_call_id = final_ctx.get("researcher_tool_call_id") or "tc_001"
            tool_events = [
                ToolEvent(
                    tool_name="tavily_search",
                    input="(via swarm)",
                    output=f"{len(final_ctx.get('retrieved_sources') or [])} results",
                    status="success",
                    evidence_id="ev_001",
                    timestamp=now,
                )
            ]
            context_delta = {
                "retrieved_sources": final_ctx.get("retrieved_sources") or [],
                "tool_events": tool_events,
            }
        elif name == "VerifierAgent":
            raw_id = final_ctx.get("verifier_tool_call_id") or ""
            tool_call_id = raw_id or None
            context_delta = {
                "verified_sources_count": final_ctx.get("verified_sources_count") or 0,
            }
        elif name == "ReporterAgent":
            context_delta = {"final_output": final_ctx.get("final_output") or {}}
        elif name == "HumanGateAgent":
            context_delta = {
                "approval_status": final_ctx.get("approval_status") or "pending",
            }

        events.append(
            TraceEvent(
                step=agent_to_step[name],
                agent=name,
                type="agent_turn",
                content=str(content)[:2000],
                tool_call_id=tool_call_id,
                context_delta=context_delta,
                handoff_to=None,
                timestamp=now,
            )
        )

    for i, ev in enumerate(events):
        ev.handoff_to = events[i + 1].agent if i + 1 < len(events) else None

    return events


SWARM_TRACE_PATH = "zone_b/fixtures/swarm_trace.json"


FailureMode = Literal[
    "force_no_evidence",
    "force_no_tool_call",
    "force_routing_break",
    "force_no_approval",
    "force_malformed_output",
]


def _synthesize_stub_run(
    task: str,
    research_question: str,
    failure_mode: FailureMode | None = None,
) -> tuple[list[TraceEvent], ContextVariables]:
    """Build a deterministic 6-event trace without any LLM or Tavily call.

    With ``failure_mode=None`` produces a clean trace that passes all Zone B
    contract checks. With ``failure_mode="force_*"`` produces a trace that
    triggers exactly one Zone B contract violation type:

    - force_no_evidence       → evidence violation (verified_sources_count = 0)
    - force_no_tool_call      → tool violation (verifier missing tool_call_id)
    - force_routing_break     → routing violation (verifier tool_event not success)
    - force_no_approval       → approval violation (approval_status != approved)
    - force_malformed_output  → schema violation (final_output missing keys)

    Each force_* mode keeps the OTHER four contracts passing, so contract
    checker output is exactly {expected_contract_type}.
    """
    now = 0.0  # fixed timestamp keeps stub mode fully deterministic across runs

    # Per-mode toggles. Each force_* mode flips exactly one knob so Zone B
    # produces exactly one violation type. Defaults below are the clean path.
    verified_sources_count = 1
    verifier_tool_call_id_value: str | None = "tc_v01"
    verifier_tool_event_status = "success"
    approval_status_value = "approved"
    approval_granted_value = True
    final_output_complete = True

    if failure_mode == "force_no_evidence":
        verified_sources_count = 0
    elif failure_mode == "force_no_tool_call":
        verifier_tool_call_id_value = None
    elif failure_mode == "force_routing_break":
        # Tool contract uses the EVENT-level tool_call_id, so keep it set.
        # Routing contract requires a SUCCESSFUL verifier tool_event preceding
        # Reporter — flip status to "failure" to break routing without
        # tripping the tool contract.
        verifier_tool_event_status = "failure"
    elif failure_mode == "force_no_approval":
        approval_status_value = "pending"
        approval_granted_value = False
    elif failure_mode == "force_malformed_output":
        final_output_complete = False

    if final_output_complete:
        stub_final_output: dict[str, Any] = {
            "summary": f"Stub summary for: {task}",
            "claims": ["Stub claim from verified sources."],
            "citations": ["https://stub.example.com/source-1"],
            "risks": ["No real risks — this is a stub trace."],
            "next_steps": ["Replace stub with a live swarm run for production results."],
        }
    else:
        # Drop required keys to trigger the schema contract
        stub_final_output = {"summary": f"Stub malformed for: {task}"}

    verifier_tool_event = ToolEvent(
        tool_name="tavily_search",
        input=research_question,
        output="stub verified result"
        if verifier_tool_event_status == "success"
        else "stub verification failed",
        status=verifier_tool_event_status,
        evidence_id="ev_stub_01",
        timestamp=now,
    )

    events: list[TraceEvent] = [
        TraceEvent(
            step=1,
            agent="ResearcherAgent",
            type="agent_turn",
            content=f"[stub] Retrieved 1 source for: {research_question}",
            tool_call_id="tc_r01",
            context_delta={
                "retrieved_sources": [{"title": "Stub Source", "url": "https://stub.example.com/source-1", "snippet": "Stub snippet."}],
                "tool_events": [
                    ToolEvent(
                        tool_name="tavily_search",
                        input=research_question,
                        output="stub search result",
                        status="success",
                        evidence_id="ev_stub_00",
                        timestamp=now,
                    )
                ],
            },
            handoff_to="CriticAgent",
            timestamp=now,
        ),
        TraceEvent(
            step=2,
            agent="CriticAgent",
            type="agent_turn",
            content="[stub] Sources look credible — no major risks identified.",
            tool_call_id=None,
            context_delta={},
            handoff_to="VerifierAgent",
            timestamp=now,
        ),
        TraceEvent(
            step=3,
            agent="VerifierAgent",
            type="agent_turn",
            content=(
                f"[stub] Verified {verified_sources_count} source(s). "
                f"tool_call_id: {verifier_tool_call_id_value or 'null'}"
            ),
            tool_call_id=verifier_tool_call_id_value,
            context_delta={
                "verified_sources_count": verified_sources_count,
                "tool_events": [verifier_tool_event],
            },
            handoff_to="ReporterAgent",
            timestamp=now,
        ),
        TraceEvent(
            step=4,
            agent="ReporterAgent",
            type="agent_turn",
            content="[stub] Final memo produced.",
            tool_call_id=None,
            context_delta={"final_output": stub_final_output},
            handoff_to="HumanGateAgent",
            timestamp=now,
        ),
        TraceEvent(
            step=5,
            agent="HumanGateAgent",
            type="agent_turn",
            content=f"[stub] Report approval status: {approval_status_value}.",
            tool_call_id=None,
            context_delta={"approval_status": approval_status_value},
            handoff_to="ActionAgent",
            timestamp=now,
        ),
        TraceEvent(
            step=6,
            agent="ActionAgent",
            type="agent_turn",
            content="[stub] Action recorded — report saved.",
            tool_call_id=None,
            context_delta={},
            handoff_to=None,
            timestamp=now,
        ),
    ]

    ctx = ContextVariables(
        data={
            "retrieved_sources": [{"title": "Stub Source", "url": "https://stub.example.com/source-1", "snippet": "Stub snippet."}],
            "researcher_tool_call_id": "tc_r01",
            "researcher_summary": f"Stub summary for: {task}",
            "critique_notes": ["Stub critique note."],
            "risk_flags": [],
            "verified_sources_count": verified_sources_count,
            "verifier_tool_call_id": verifier_tool_call_id_value or "",
            "verifier_narrative": "Stub verification passed."
            if verified_sources_count > 0
            else "Stub verification failed: no sources verified.",
            "sources_verified": verified_sources_count > 0,
            "final_output": stub_final_output,
            "approval_granted": approval_granted_value,
            "approval_status": approval_status_value,
            "approval_comments": "Stub approval granted."
            if approval_granted_value
            else "Stub approval denied.",
            "action_taken": "Report saved to disk (stub).",
        }
    )
    return events, ctx


async def run_swarm(
    task: str | None = None,
    research_question: str | None = None,
    run_id: str = "swarm_001",
    interactive: bool = False,
    fixture_path: str | Path | None = "zone_a/fixtures/task.json",
    output_path: str | Path = SWARM_TRACE_PATH,
    mode: Literal["live", "stub"] = "live",
    failure_mode: FailureMode | None = None,
) -> dict[str, Any]:
    """Run the Zone A swarm and emit a trace JSON for Zone B to consume.

    ``mode="stub"`` skips ``a_initiate_group_chat`` and Tavily entirely,
    synthesising a deterministic 6-event clean trace for offline testing.
    ``mode="live"`` (default) preserves all existing behaviour.

    The swarm produces a *partial* trace when it terminates early on a
    contract violation. Output defaults to ``zone_b/fixtures/swarm_trace.json``
    so the historical 5-event fixture (used by the existing test suite)
    stays untouched.

    Returns a summary dict with the final ContextVariables snapshot, the
    trace events, the last agent reached, and whether the swarm terminated
    early due to a contract violation.
    """
    if task is None or research_question is None:
        if fixture_path is None:
            raise ValueError("task/research_question or fixture_path required")
        fixture = json.loads(Path(fixture_path).read_text())
        task = task or fixture["task"]
        research_question = research_question or fixture["research_question"]
        run_id = fixture.get("run_id", run_id)

    if mode == "stub":
        events, final_ctx = _synthesize_stub_run(
            task, research_question, failure_mode=failure_mode
        )
        last_agent_name: str | None = "ActionAgent"
    elif mode == "live":
        if failure_mode is not None:
            raise ValueError("failure_mode is only supported in stub mode")
        agents, ctx = build_swarm(interactive=interactive)
        initial_message = _build_initial_message(task, research_question)

        pattern = RoundRobinPattern(
            initial_agent=agents[0],
            agents=agents,
            context_variables=ctx,
            group_after_work=TerminateTarget(),
        )

        chat_result, final_ctx, last_agent = await a_initiate_group_chat(
            pattern=pattern,
            messages=initial_message,
            max_rounds=18,
        )

        events = _chat_history_to_trace_events(chat_result.chat_history, final_ctx)
        last_agent_name = last_agent.name if last_agent else None
    else:
        raise ValueError(f"unknown mode: {mode!r} (expected 'live' or 'stub')")

    snapshot = ContextSnapshot(
        retrieved_sources=final_ctx.get("retrieved_sources") or [],
        verified_sources_count=final_ctx.get("verified_sources_count") or 0,
        tool_events=[
            te
            for e in events
            for te in (e.context_delta.get("tool_events") or [])
            if isinstance(te, ToolEvent)
        ],
        approval_status=final_ctx.get("approval_status") or "pending",
        failed_agent=last_agent_name,
        failed_step=len(events),
        final_output=final_ctx.get("final_output"),
    )

    written = emit_trace(snapshot, events, run_id=run_id, output_path=output_path)

    terminated_early = len(events) < 6
    return {
        "events": events,
        "context": final_ctx,
        "last_agent": last_agent_name,
        "terminated_early": terminated_early,
        "trace_path": str(written),
    }


if __name__ == "__main__":
    result = asyncio.run(run_swarm(interactive=False))
    print(f"\nSwarm finished — last agent: {result['last_agent']}")
    print(f"Events recorded: {len(result['events'])}")
    print(f"Terminated early (contract violation): {result['terminated_early']}")
    print(f"Trace written to: {result['trace_path']}")
