"""ContextVariables-updating tools for the Zone A swarm.

Each tool takes a `context_variables: ContextVariables` parameter — AG2's
GroupToolExecutor injects the shared ContextVariables instance automatically
when the parameter is named exactly that.

The tools are the bridge between LLM-emitted JSON and the typed state that
OnContextCondition handoffs read to decide routing.
"""
from autogen.agentchat.group import ContextVariables, ReplyResult


def record_research(
    retrieved_sources: list[dict],
    tool_call_id: str,
    summary: str,
    context_variables: ContextVariables,
) -> ReplyResult:
    """ResearcherAgent records its Tavily search results."""
    context_variables.set("retrieved_sources", retrieved_sources)
    context_variables.set("researcher_tool_call_id", tool_call_id)
    context_variables.set("researcher_summary", summary)
    return ReplyResult(
        message=f"Recorded {len(retrieved_sources)} sources (tool_call_id={tool_call_id}).",
        context_variables=context_variables,
    )


def record_critique(
    critique_notes: list[str],
    risk_flags: list[str],
    context_variables: ContextVariables,
) -> ReplyResult:
    """CriticAgent records critique notes and risk flags."""
    context_variables.set("critique_notes", critique_notes)
    context_variables.set("risk_flags", risk_flags)
    return ReplyResult(
        message=f"Recorded {len(critique_notes)} critique notes, {len(risk_flags)} risks.",
        context_variables=context_variables,
    )


def record_verification(
    verified_sources_count: int,
    tool_call_id: str | None,
    narrative: str,
    context_variables: ContextVariables,
) -> ReplyResult:
    """VerifierAgent records verification results.

    Sets the C1 (sources_verified) and C2 (tool_call_id present) gates that
    OnContextCondition handoffs read. If verified_sources_count is 0 OR
    tool_call_id is missing, sources_verified stays False — terminating the swarm.
    """
    context_variables.set("verified_sources_count", verified_sources_count)
    context_variables.set("verifier_tool_call_id", tool_call_id or "")
    context_variables.set("verifier_narrative", narrative)
    sources_verified = verified_sources_count > 0 and bool(tool_call_id)
    context_variables.set("sources_verified", sources_verified)
    msg = (
        f"Verification recorded: count={verified_sources_count}, "
        f"tool_call_id={tool_call_id}, sources_verified={sources_verified}"
    )
    return ReplyResult(message=msg, context_variables=context_variables)


def record_report(
    summary: str,
    claims: list[str],
    citations: list[str],
    risks: list[str],
    next_steps: list[str],
    context_variables: ContextVariables,
) -> ReplyResult:
    """ReporterAgent records the final structured report."""
    final_output = {
        "summary": summary,
        "claims": claims,
        "citations": citations,
        "risks": risks,
        "next_steps": next_steps,
    }
    context_variables.set("final_output", final_output)
    return ReplyResult(
        message=f"Report recorded: {len(claims)} claims, {len(citations)} citations.",
        context_variables=context_variables,
    )


def record_approval(
    approval_granted: bool,
    comments: str,
    context_variables: ContextVariables,
) -> ReplyResult:
    """HumanGateAgent records the human approval decision.

    Sets the C3 (approval_granted) gate. ActionAgent only runs if True.
    """
    context_variables.set("approval_granted", approval_granted)
    context_variables.set(
        "approval_status", "approved" if approval_granted else "pending"
    )
    context_variables.set("approval_comments", comments)
    return ReplyResult(
        message=f"Approval recorded: granted={approval_granted}",
        context_variables=context_variables,
    )


def record_action(
    action_taken: str,
    context_variables: ContextVariables,
) -> ReplyResult:
    """ActionAgent records the side-effect it performed."""
    context_variables.set("action_taken", action_taken)
    return ReplyResult(
        message=f"Action recorded: {action_taken}",
        context_variables=context_variables,
    )
