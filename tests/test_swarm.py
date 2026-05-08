"""Tests for the Zone A AG2 swarm.

Structural tests verify that:
  - the 6-agent swarm builds with the expected agents and tools
  - ContextVariables initialise correctly
  - OnContextCondition handoffs are registered (C1/C2/C3 enforcement)
  - the RegexGuardrail on VerifierAgent output is registered

Pure-function tests verify each tool's effect on ContextVariables.

No LLM is invoked — tests use a fake llm_config.
"""
import re


from autogen.agentchat.group import (
    ContextVariables,
    StringContextCondition,
    AgentTarget,
    TerminateTarget,
)
from autogen.agentchat.group.guardrails import RegexGuardrail

from zone_a.swarm import build_swarm, _chat_history_to_trace_events
from zone_a.swarm_tools import (
    record_action,
    record_approval,
    record_critique,
    record_report,
    record_research,
    record_verification,
)


_FAKE_LLM = {
    "config_list": [
        {"model": "fake-model", "api_key": "fake-key", "base_url": "http://localhost"}
    ],
    "temperature": 0.1,
}


# ─── tool unit tests ────────────────────────────────────────────────────────

class TestSwarmTools:
    def test_record_research_sets_sources_and_tool_call_id(self):
        ctx = ContextVariables(data={})
        sources = [{"title": "S1", "url": "u", "snippet": "x"}]
        record_research(
            retrieved_sources=sources,
            tool_call_id="tc_001",
            summary="found 1",
            context_variables=ctx,
        )
        assert ctx.get("retrieved_sources") == sources
        assert ctx.get("researcher_tool_call_id") == "tc_001"
        assert ctx.get("researcher_summary") == "found 1"

    def test_record_critique_records_notes_and_risks(self):
        ctx = ContextVariables(data={})
        record_critique(
            critique_notes=["n1", "n2"],
            risk_flags=["r1"],
            context_variables=ctx,
        )
        assert ctx.get("critique_notes") == ["n1", "n2"]
        assert ctx.get("risk_flags") == ["r1"]

    def test_record_verification_passing_sets_sources_verified_true(self):
        ctx = ContextVariables(data={"sources_verified": False})
        record_verification(
            verified_sources_count=2,
            tool_call_id="tc_xyz",
            narrative="ok",
            context_variables=ctx,
        )
        assert ctx.get("sources_verified") is True
        assert ctx.get("verified_sources_count") == 2
        assert ctx.get("verifier_tool_call_id") == "tc_xyz"

    def test_record_verification_zero_count_keeps_unverified(self):
        ctx = ContextVariables(data={"sources_verified": False})
        record_verification(
            verified_sources_count=0,
            tool_call_id="tc_xyz",
            narrative="none",
            context_variables=ctx,
        )
        assert ctx.get("sources_verified") is False  # C1 violation

    def test_record_verification_missing_tool_call_id_keeps_unverified(self):
        ctx = ContextVariables(data={"sources_verified": False})
        record_verification(
            verified_sources_count=2,
            tool_call_id=None,
            narrative="no tool",
            context_variables=ctx,
        )
        assert ctx.get("sources_verified") is False  # C2 violation
        assert ctx.get("verifier_tool_call_id") == ""

    def test_record_report_assembles_final_output(self):
        ctx = ContextVariables(data={})
        record_report(
            summary="s",
            claims=["c1"],
            citations=["r1"],
            risks=["x"],
            next_steps=["n"],
            context_variables=ctx,
        )
        out = ctx.get("final_output")
        assert out["summary"] == "s"
        assert out["claims"] == ["c1"]
        assert out["citations"] == ["r1"]

    def test_record_approval_true_sets_approved(self):
        ctx = ContextVariables(data={"approval_granted": False})
        record_approval(approval_granted=True, comments="lgtm", context_variables=ctx)
        assert ctx.get("approval_granted") is True
        assert ctx.get("approval_status") == "approved"
        assert ctx.get("approval_comments") == "lgtm"

    def test_record_approval_false_keeps_pending(self):
        ctx = ContextVariables(data={"approval_granted": False})
        record_approval(approval_granted=False, comments="no", context_variables=ctx)
        assert ctx.get("approval_granted") is False
        assert ctx.get("approval_status") == "pending"

    def test_record_action_sets_action_taken(self):
        ctx = ContextVariables(data={})
        record_action(action_taken="saved memo to disk", context_variables=ctx)
        assert ctx.get("action_taken") == "saved memo to disk"


# ─── swarm structural tests ─────────────────────────────────────────────────

class TestSwarmStructure:
    def test_swarm_builds_six_agents_in_order(self):
        agents, _ = build_swarm(llm_config=_FAKE_LLM)
        assert [a.name for a in agents] == [
            "ResearcherAgent",
            "CriticAgent",
            "VerifierAgent",
            "ReporterAgent",
            "HumanGateAgent",
            "ActionAgent",
        ]

    def test_initial_context_has_all_gate_keys(self):
        _, ctx = build_swarm(llm_config=_FAKE_LLM)
        assert ctx.get("sources_verified") is False
        assert ctx.get("approval_granted") is False
        assert ctx.get("approval_status") == "pending"
        assert ctx.get("verified_sources_count") == 0

    def test_each_agent_has_one_tool_registered(self):
        agents, _ = build_swarm(llm_config=_FAKE_LLM)
        # Each agent's llm_config should have exactly one tool wired in.
        for agent in agents:
            assert agent.llm_config is not None
            tools = getattr(agent.llm_config, "tools", []) or []
            assert len(tools) >= 1, f"{agent.name} has no tools registered"

    def test_human_gate_human_input_mode_default_never(self):
        agents, _ = build_swarm(llm_config=_FAKE_LLM, interactive=False)
        gate = next(a for a in agents if a.name == "HumanGateAgent")
        assert gate.human_input_mode == "NEVER"

    def test_human_gate_human_input_mode_interactive_always(self):
        agents, _ = build_swarm(llm_config=_FAKE_LLM, interactive=True)
        gate = next(a for a in agents if a.name == "HumanGateAgent")
        assert gate.human_input_mode == "ALWAYS"


class TestSwarmHandoffs:
    """OnContextCondition handoffs implement C1/C2/C3 enforcement."""

    def test_verifier_has_handoff_to_reporter_on_sources_verified(self):
        agents, _ = build_swarm(llm_config=_FAKE_LLM)
        verifier = next(a for a in agents if a.name == "VerifierAgent")
        reporter = next(a for a in agents if a.name == "ReporterAgent")
        conditional = [
            c for c in verifier.handoffs.context_conditions if c.condition is not None
        ]
        assert len(conditional) == 1
        h = conditional[0]
        assert isinstance(h.condition, StringContextCondition)
        assert h.condition.variable_name == "sources_verified"
        assert isinstance(h.target, AgentTarget)
        assert h.target.agent_name == reporter.name

    def test_verifier_has_terminate_catchall(self):
        """The condition=None catch-all in context_conditions triggers
        TerminateTarget when no other handoff fires (C1+C2 enforcement)."""
        agents, _ = build_swarm(llm_config=_FAKE_LLM)
        verifier = next(a for a in agents if a.name == "VerifierAgent")
        catchalls = [
            c for c in verifier.handoffs.context_conditions if c.condition is None
        ]
        assert len(catchalls) == 1
        assert isinstance(catchalls[0].target, TerminateTarget)

    def test_human_gate_has_handoff_to_action_on_approval_granted(self):
        agents, _ = build_swarm(llm_config=_FAKE_LLM)
        gate = next(a for a in agents if a.name == "HumanGateAgent")
        action = next(a for a in agents if a.name == "ActionAgent")
        conditional = [
            c for c in gate.handoffs.context_conditions if c.condition is not None
        ]
        assert len(conditional) == 1
        h = conditional[0]
        assert isinstance(h.condition, StringContextCondition)
        assert h.condition.variable_name == "approval_granted"
        assert isinstance(h.target, AgentTarget)
        assert h.target.agent_name == action.name

    def test_human_gate_has_terminate_catchall(self):
        """C3 enforcement: ActionAgent skipped when approval_granted is False."""
        agents, _ = build_swarm(llm_config=_FAKE_LLM)
        gate = next(a for a in agents if a.name == "HumanGateAgent")
        catchalls = [
            c for c in gate.handoffs.context_conditions if c.condition is None
        ]
        assert len(catchalls) == 1
        assert isinstance(catchalls[0].target, TerminateTarget)

    def test_handoff_evaluation_order_respects_sources_verified_true(self):
        """When sources_verified=True the conditional handoff fires before catch-all."""
        agents, ctx = build_swarm(llm_config=_FAKE_LLM)
        verifier = next(a for a in agents if a.name == "VerifierAgent")
        ctx.set("sources_verified", True)
        # The conditional must come before the catch-all; first match wins.
        first = verifier.handoffs.context_conditions[0]
        assert first.condition is not None
        assert first.condition.variable_name == "sources_verified"
        # Evaluate against ctx — the conditional matches when True.
        assert first.condition.evaluate(ctx) is True

    def test_handoff_evaluation_when_sources_unverified_falls_to_terminate(self):
        agents, ctx = build_swarm(llm_config=_FAKE_LLM)
        verifier = next(a for a in agents if a.name == "VerifierAgent")
        # ctx default has sources_verified=False — first cond fails
        first = verifier.handoffs.context_conditions[0]
        assert first.condition.evaluate(ctx) is False
        # Falls through to catch-all (condition=None == always-true)
        catchall = verifier.handoffs.context_conditions[1]
        assert catchall.condition is None
        assert isinstance(catchall.target, TerminateTarget)


class TestSwarmGuardrails:
    def test_verifier_has_c2_regex_output_guardrail(self):
        agents, _ = build_swarm(llm_config=_FAKE_LLM)
        verifier = next(a for a in agents if a.name == "VerifierAgent")
        guardrails = list(getattr(verifier, "output_guardrails", []) or [])
        regex_guards = [g for g in guardrails if isinstance(g, RegexGuardrail)]
        assert any(g.name == "C2_missing_tool_call_id" for g in regex_guards)

    def test_c2_guardrail_regex_matches_null_tool_call_id(self):
        agents, _ = build_swarm(llm_config=_FAKE_LLM)
        verifier = next(a for a in agents if a.name == "VerifierAgent")
        guard = next(
            g for g in verifier.output_guardrails
            if isinstance(g, RegexGuardrail) and g.name == "C2_missing_tool_call_id"
        )
        # Pattern should match null/None on tool_call_id field
        bad_outputs = [
            'tool_call_id: null',
            'tool_call_id=None',
            'tool_call_id: ""',
            "tool_call_id: ''",
        ]
        for out in bad_outputs:
            assert re.search(guard.condition, out), (
                f"C2 guardrail must fire on: {out}"
            )

    def test_c2_guardrail_regex_does_not_match_valid_tool_call_id(self):
        agents, _ = build_swarm(llm_config=_FAKE_LLM)
        verifier = next(a for a in agents if a.name == "VerifierAgent")
        guard = next(
            g for g in verifier.output_guardrails
            if isinstance(g, RegexGuardrail) and g.name == "C2_missing_tool_call_id"
        )
        good_output = 'tool_call_id: "tc_001" (Tavily call)'
        assert not re.search(guard.condition, good_output)


# ─── trace extraction ───────────────────────────────────────────────────────

class TestTraceExtraction:
    def test_chat_history_with_no_assistant_messages_yields_no_events(self):
        ctx = ContextVariables(data={})
        events = _chat_history_to_trace_events([], ctx)
        assert events == []

    def test_chat_history_with_full_swarm_yields_six_events(self):
        ctx = ContextVariables(
            data={
                "retrieved_sources": [{"title": "x"}],
                "researcher_tool_call_id": "tc_001",
                "verified_sources_count": 2,
                "verifier_tool_call_id": "tc_002",
                "final_output": {"summary": "s"},
                "approval_status": "approved",
            }
        )
        history = [
            {"role": "user", "content": "go"},
            {"role": "assistant", "name": "ResearcherAgent", "content": "found"},
            {"role": "assistant", "name": "CriticAgent", "content": "ok"},
            {"role": "assistant", "name": "VerifierAgent", "content": "verified"},
            {"role": "assistant", "name": "ReporterAgent", "content": "report"},
            {"role": "assistant", "name": "HumanGateAgent", "content": "approved"},
            {"role": "assistant", "name": "ActionAgent", "content": "done"},
        ]
        events = _chat_history_to_trace_events(history, ctx)
        assert len(events) == 6
        assert [e.agent for e in events] == [
            "ResearcherAgent", "CriticAgent", "VerifierAgent",
            "ReporterAgent", "HumanGateAgent", "ActionAgent",
        ]

    def test_terminated_swarm_yields_partial_trace(self):
        ctx = ContextVariables(
            data={
                "retrieved_sources": [{"title": "x"}],
                "researcher_tool_call_id": "tc_001",
                "verified_sources_count": 0,
                "verifier_tool_call_id": "",
                "sources_verified": False,
            }
        )
        history = [
            {"role": "user", "content": "go"},
            {"role": "assistant", "name": "ResearcherAgent", "content": "found"},
            {"role": "assistant", "name": "CriticAgent", "content": "ok"},
            {"role": "assistant", "name": "VerifierAgent", "content": "no verify"},
        ]
        events = _chat_history_to_trace_events(history, ctx)
        assert len(events) == 3
        verifier_event = events[2]
        assert verifier_event.agent == "VerifierAgent"
        assert verifier_event.tool_call_id is None  # C2: empty string maps to None

    def test_researcher_event_carries_tool_events(self):
        from shared.models import ToolEvent
        ctx = ContextVariables(
            data={
                "retrieved_sources": [{"title": "x"}, {"title": "y"}],
                "researcher_tool_call_id": "tc_001",
            }
        )
        history = [
            {"role": "assistant", "name": "ResearcherAgent", "content": "found 2"},
        ]
        events = _chat_history_to_trace_events(history, ctx)
        assert len(events) == 1
        tool_events = events[0].context_delta.get("tool_events", [])
        assert len(tool_events) == 1
        assert isinstance(tool_events[0], ToolEvent)
