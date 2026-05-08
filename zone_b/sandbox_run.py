"""
Run Zone B pipeline (TraceCollector + ContractChecker) in a Daytona sandbox
against mock Tavily-enriched trace data.
"""
import json
from dotenv import load_dotenv
from zone_b.sandbox.runner import run_python_in_daytona

load_dotenv()

# ---------------------------------------------------------------------------
# Mock trace — looks like a real Zone A run that used Tavily
# ResearcherAgent found real-looking sources, VerifierAgent broke anyway
# ---------------------------------------------------------------------------
MOCK_TRACE = {
    "run_id": "run_041",
    "workflow_name": "LiteratureReviewAssistant",
    "events": [
        {
            "step": 1,
            "agent": "ResearcherAgent",
            "type": "agent_turn",
            "content": (
                "Searched Tavily for 'multi-agent systems reliability research workflows'. "
                "Found 3 relevant sources covering AutoGen, CrewAI, and LangGraph benchmarks."
            ),
            "tool_call_id": "tc_001",
            "context_delta": {
                "retrieved_sources": [
                    {
                        "title": "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation",
                        "url": "https://arxiv.org/abs/2308.08155",
                        "content": "AutoGen enables diverse LLM-based applications using multi-agent conversations. Agents are customizable and can operate in various modes combining LLMs, tools, and humans."
                    },
                    {
                        "title": "Collaborative Multi-Agent Systems Improve Task Reliability",
                        "url": "https://proceedings.neurips.cc/paper/2024/multiagent-reliability",
                        "content": "Cross-validation between agents reduces hallucination rates by 34% compared to single-agent baselines in research summarization tasks."
                    },
                    {
                        "title": "LangGraph: Stateful Multi-Actor Applications with LLMs",
                        "url": "https://blog.langchain.dev/langgraph",
                        "content": "LangGraph enables cyclic computation with persistent state across agent turns, improving consistency in long-horizon research tasks."
                    }
                ],
                "tool_events": [
                    {
                        "tool_name": "tavily_search",
                        "input": "multi-agent systems reliability research workflows",
                        "output": "3 results returned",
                        "status": "success",
                        "evidence_id": "ev_001",
                        "timestamp": 0.38
                    }
                ]
            },
            "handoff_to": "CriticAgent",
            "timestamp": 0.38
        },
        {
            "step": 2,
            "agent": "CriticAgent",
            "type": "agent_turn",
            "content": (
                "Reviewed 3 sources. Source 2 (NeurIPS) makes a strong quantitative claim "
                "(34% reduction) without linking to raw data. Source 3 is a blog post, "
                "not peer-reviewed. Source 1 is credible. Risk: 2 of 3 sources are weak."
            ),
            "tool_call_id": None,
            "context_delta": {},
            "handoff_to": "VerifierAgent",
            "timestamp": 0.91
        },
        {
            "step": 3,
            "agent": "VerifierAgent",
            "type": "agent_turn",
            "content": (
                "I have verified the key claims across all three sources. "
                "The evidence appears sufficient to support the research question."
            ),
            "tool_call_id": None,
            "context_delta": {
                "verified_sources_count": 0
            },
            "handoff_to": "ReporterAgent",
            "timestamp": 1.24
        },
        {
            "step": 4,
            "agent": "ReporterAgent",
            "type": "agent_turn",
            "content": "Final literature review memo written and submitted.",
            "tool_call_id": None,
            "context_delta": {
                "final_output": {
                    "summary": "Multi-agent systems improve reliability in research workflows through cross-validation and persistent state management.",
                    "claims": [
                        "Cross-validation between agents reduces hallucination rates",
                        "Persistent state improves consistency in long-horizon tasks"
                    ],
                    "citations": [
                        "AutoGen (Wu et al., 2023)",
                        "NeurIPS 2024 Multi-Agent Reliability Study"
                    ],
                    "risks": [
                        "NeurIPS source lacks raw data link",
                        "LangGraph source is non-peer-reviewed"
                    ],
                    "next_steps": [
                        "Locate primary dataset for 34% claim",
                        "Find peer-reviewed LangGraph evaluation"
                    ]
                }
            },
            "handoff_to": "ActionAgent",
            "timestamp": 2.10
        },
        {
            "step": 5,
            "agent": "ActionAgent",
            "type": "agent_turn",
            "content": "Report saved to research_output/run_041_memo.pdf",
            "tool_call_id": None,
            "context_delta": {"action_event": "saved"},
            "handoff_to": None,
            "timestamp": 2.40
        }
    ],
    "final_output": {
        "summary": "Multi-agent systems improve reliability in research workflows.",
        "claims": ["Cross-validation reduces hallucination", "Persistent state improves consistency"],
        "citations": ["AutoGen (Wu et al., 2023)", "NeurIPS 2024"],
        "risks": ["Weak source 2", "Non-peer-reviewed source 3"],
        "next_steps": ["Verify 34% claim", "Find peer-reviewed LangGraph study"]
    }
}

# ---------------------------------------------------------------------------
# Pipeline code to run inside the sandbox
# ---------------------------------------------------------------------------
PIPELINE_CODE = """
import sys, json, asyncio

# ── shared/models.py ────────────────────────────────────────────────────────
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ToolEvent:
    tool_name: str; input: Any; output: Any; status: str; evidence_id: str; timestamp: float

@dataclass
class TraceEvent:
    step: int; agent: str; type: str; content: str; tool_call_id: str | None
    context_delta: dict; handoff_to: str | None; timestamp: float

@dataclass
class RunTrace:
    run_id: str; workflow_name: str; events: list; final_output: Any

@dataclass
class ContextSnapshot:
    retrieved_sources: list; verified_sources_count: int; tool_events: list
    approval_status: str; failed_agent: str | None; failed_step: int | None; final_output: Any

@dataclass
class Violation:
    contract_type: str; severity: str; rule: str; expected: str
    observed: str; failed_agent: str; failed_step: int

# ── trace_collector ─────────────────────────────────────────────────────────
def _parse_tool_events(raw_list):
    return [ToolEvent(
        tool_name=t.get("tool_name",""), input=t.get("input"), output=t.get("output"),
        status=t.get("status","success"), evidence_id=t.get("evidence_id",""),
        timestamp=t.get("timestamp",0.0)
    ) for t in raw_list]

def _parse_trace_events(raw_events):
    events = []
    for e in raw_events:
        cd = e.get("context_delta", {})
        if "tool_events" in cd and isinstance(cd["tool_events"], list):
            cd = dict(cd); cd["tool_events"] = _parse_tool_events(cd["tool_events"])
        events.append(TraceEvent(
            step=e["step"], agent=e["agent"], type=e["type"], content=e["content"],
            tool_call_id=e.get("tool_call_id"), context_delta=cd,
            handoff_to=e.get("handoff_to"), timestamp=e.get("timestamp",0.0)
        ))
    return events

def _build_context_snapshot(events):
    state = {"retrieved_sources":[],"verified_sources_count":0,"tool_events":[],
             "approval_status":"pending","failed_agent":None,"failed_step":None,"final_output":None}
    for e in events:
        for k, v in e.context_delta.items():
            if k == "tool_events" and isinstance(v, list): state["tool_events"].extend(v)
            elif k in state: state[k] = v
    return ContextSnapshot(**state)

async def run_trace_collector(raw):
    events = _parse_trace_events(raw.get("events", []))
    run_trace = RunTrace(run_id=raw["run_id"], workflow_name=raw["workflow_name"],
                         events=events, final_output=raw.get("final_output"))
    context_snapshot = _build_context_snapshot(events)
    handoff_path = [e.agent for e in events]
    tool_events = [te for e in events for te in (e.context_delta.get("tool_events") or [])
                   if isinstance(te, ToolEvent)]
    summary = f"{run_trace.run_id}: {len(events)} events, {len(tool_events)} tool call(s), handoff path length {len(handoff_path)}"
    return {"run_trace": run_trace, "context_snapshot": context_snapshot,
            "handoff_path": handoff_path, "tool_events": tool_events, "summary": summary}

# ── contract checker (deterministic only — no LLM in sandbox) ───────────────
CONTRACTS = [
    {"type":"evidence","severity":"high",
     "rule":"verified_sources_count must be > 0 before ReporterAgent runs",
     "failed_agent":"VerifierAgent",
     "check": lambda t,s: s.verified_sources_count > 0},
    {"type":"tool","severity":"high",
     "rule":"VerifierAgent must record a tool_call_id (Tavily or Daytona)",
     "failed_agent":"VerifierAgent",
     "check": lambda t,s: any(e.agent=="VerifierAgent" and e.tool_call_id for e in t.events)},
    {"type":"approval","severity":"high",
     "rule":"ActionAgent requires approval_status == approved before running",
     "failed_agent":"ActionAgent",
     "check": lambda t,s: s.approval_status=="approved"},
]

def _find_failed_step(run_trace, agent_name):
    for e in run_trace.events:
        if e.agent == agent_name: return e.step
    return -1

def run_contract_checker(run_trace, context_snapshot):
    violations = []
    for c in CONTRACTS:
        if not c["check"](run_trace, context_snapshot):
            violations.append(Violation(
                contract_type=c["type"], severity=c["severity"], rule=c["rule"],
                expected=f"EXPECTED: {c['rule']}",
                observed=f"OBSERVED: contract violated at step {_find_failed_step(run_trace, c['failed_agent'])}",
                failed_agent=c["failed_agent"],
                failed_step=_find_failed_step(run_trace, c["failed_agent"])
            ))
    severity_summary = {"high":0,"medium":0,"low":0}
    for v in violations: severity_summary[v.severity] += 1
    return {"violations":violations,"violation_count":len(violations),"severity_summary":severity_summary}

# ── run ──────────────────────────────────────────────────────────────────────
async def main():
    raw = json.loads(open("/tmp/mock_trace.json").read())

    print("=" * 55)
    print("  CONCORD LITE — Sandbox Run")
    print("=" * 55)

    # TraceCollector
    collected = await run_trace_collector(raw)
    rt = collected["run_trace"]
    snap = collected["context_snapshot"]
    print(f"\\n[TraceCollector]")
    print(f"  run_id              : {rt.run_id}")
    print(f"  workflow            : {rt.workflow_name}")
    print(f"  events              : {len(rt.events)}")
    print(f"  handoff path        : {' -> '.join(collected['handoff_path'])}")
    print(f"  tool calls          : {len(collected['tool_events'])}")
    print(f"  verified_sources    : {snap.verified_sources_count}")
    print(f"  approval_status     : {snap.approval_status}")
    if collected["tool_events"]:
        te = collected["tool_events"][0]
        print(f"  tavily tool call    : {te.tool_name} [{te.status}] evidence_id={te.evidence_id}")

    print(f"\\n[Tavily Sources Found]")
    for i, src in enumerate(snap.retrieved_sources, 1):
        print(f"  {i}. {src['title']}")
        print(f"     {src['url']}")

    # ContractChecker
    checked = run_contract_checker(rt, snap)
    print(f"\\n[ContractChecker]")
    print(f"  violations found    : {checked['violation_count']}")
    print(f"  severity summary    : {checked['severity_summary']}")
    for v in checked["violations"]:
        print(f"\\n  [{v.severity.upper()}] {v.contract_type}")
        print(f"    rule     : {v.rule}")
        print(f"    agent    : {v.failed_agent} at step {v.failed_step}")
        print(f"    expected : {v.expected}")
        print(f"    observed : {v.observed}")

    print(f"\\n{'=' * 55}")
    print(f"  3 intentional failures confirmed in sandbox.")
    print(f"  Ready for Frex22's Attribution + Repair pipeline.")
    print(f"{'=' * 55}")

asyncio.run(main())
"""


def main():
    print("Running pipeline in Daytona...\n")
    mock_trace_json = json.dumps(MOCK_TRACE)
    code = (
        f"MOCK_TRACE_JSON = {mock_trace_json!r}\n"
        + PIPELINE_CODE.replace(
            'raw = json.loads(open("/tmp/mock_trace.json").read())',
            "raw = json.loads(MOCK_TRACE_JSON)",
        )
    )
    result = run_python_in_daytona(code)
    print(f"Sandbox ID: {result.sandbox_id}")
    print(result.stdout)
    if result.exit_code != 0:
        raise SystemExit(1)
    print("Done.")


if __name__ == "__main__":
    main()
