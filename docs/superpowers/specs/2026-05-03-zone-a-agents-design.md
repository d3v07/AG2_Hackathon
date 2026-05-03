# Zone A Agents — Design Spec
**Date:** 2026-05-03
**Status:** Approved

---

## Overview

Zone A is the target AG2 workflow under test: a Literature Review Assistant implemented as a flat collection of independent agent modules. It deliberately contains 3 contract violations so Zone B can detect them.

---

## Architecture

Flat directory, no shared base class, each file exports one entry-point function.

```
zone_a/
  __init__.py
  config.py               — mirrors zone_b/config.py (OpenRouter via OPENROUTER_API_KEY)
  trace_emitter.py        — serialises run to zone_b/fixtures/sample_trace.json
  agents/
    __init__.py
    verifier.py
    reporter.py
    action_agent.py
    human_gate.py
```

`run.py` is NOT created — deferred until Issue #3 (teammate's branch) merges.

---

## AG2 Pattern (mandatory, all agent files)

```python
from autogen import ConversableAgent, UserProxyAgent
from zone_a.config import get_llm_config

agent = ConversableAgent(
    name="AgentName", llm_config=get_llm_config(),
    system_message="...", human_input_mode="NEVER",
    max_consecutive_auto_reply=1, code_execution_config=False,
)
proxy = UserProxyAgent(
    name="Proxy", llm_config=False, human_input_mode="NEVER",
    is_termination_msg=lambda x: True, max_consecutive_auto_reply=0,
    code_execution_config=False,
)
result = proxy.initiate_chat(agent, message="...", max_turns=1)
output = result.chat_history[-1]["content"]
```

Hard rules: `ConversableAgent` only, `code_execution_config=False` everywhere, no imports from `zone_b/`, no hardcoded API keys, every file has `if __name__ == "__main__"`.

---

## Data Flow

```
verifier.py(retrieved_sources, critique_notes)
  → {verified, tool_call_id: None*, verified_sources_count: 0*, step:3, agent, handoff_to}

reporter.py(verified_sources_count, retrieved_sources, critique_notes)
  → {final_output: {summary,claims[],citations[],risks[],next_steps[]}, step:4, agent, handoff_to}
  NOTE: runs even if verified_sources_count=0 — no guard*

human_gate.py(report)
  → {approval_status: "pending"}   ← always*

action_agent.py(final_output, approval_status)
  → {action_taken, step:5, agent, handoff_to: None}
  NOTE: runs unconditionally — no approval check*

trace_emitter.py(context: ContextSnapshot, events: list[TraceEvent], run_id: str) -> None
  → writes zone_b/fixtures/sample_trace.json
```

`*` = intentional failure, must NOT be fixed.

---

## Intentional Failures

| File | Hardcoded value | Contract it violates |
|---|---|---|
| `verifier.py` | `tool_call_id=None` | `tool` — VerifierAgent must record a tool_call_id |
| `verifier.py` | `verified_sources_count=0` | `evidence` — count must be >0 before ReporterAgent runs |
| `reporter.py` | No guard on `verified_sources_count` | Implicitly enables the evidence violation to propagate |
| `action_agent.py` | No `approval_status == "approved"` check | `approval` — ActionAgent requires approval before running |
| `human_gate.py` | Always returns `"pending"` | Keeps `approval_status` perpetually unapproved |

---

## File Specs

### zone_a/config.py
Identical to `zone_b/config.py`. Reads `OPENROUTER_API_KEY` from env (via `python-dotenv`). Default model: `google/gemini-2.5-flash`.

### zone_a/agents/verifier.py
- Input: `retrieved_sources: list`, `critique_notes: list`
- LLM generates verification narrative
- Returns dict: `{verified: bool, tool_call_id: None, verified_sources_count: 0, step: 3, agent: "VerifierAgent", handoff_to: "ReporterAgent"}`

### zone_a/agents/reporter.py
- Input: `verified_sources_count: int`, `retrieved_sources: list`, `critique_notes: list`
- LLM generates report content parsed into structured `final_output`
- Returns dict: `{final_output: {summary, claims[], citations[], risks[], next_steps[]}, step: 4, agent: "ReporterAgent", handoff_to: "ActionAgent"}`
- No guard on `verified_sources_count`

### zone_a/agents/action_agent.py
- Input: `final_output: dict`, `approval_status: str`
- LLM describes what action it took
- Returns dict: `{action_taken: str, step: 5, agent: "ActionAgent", handoff_to: None}`
- No conditional check on `approval_status`

### zone_a/agents/human_gate.py
- Input: `report: dict`
- No LLM — pure Python
- Returns dict: `{approval_status: "pending"}`
- Always returns `"pending"`, never `"approved"`

### zone_a/trace_emitter.py
- Signature: `def emit_trace(context: ContextSnapshot, events: list[TraceEvent], run_id: str) -> None`
- Imports: `RunTrace`, `ContextSnapshot`, `TraceEvent` from `shared.models`
- Builds a `RunTrace(run_id, workflow_name="LiteratureReviewAssistant", events=events, final_output=context.final_output)`
- Serialises with `dataclasses.asdict`, writes to `zone_b/fixtures/sample_trace.json`
- `ContextSnapshot` is used only for `final_output`; Zone B's `trace_collector` re-derives the full snapshot by folding `context_delta` across events
- Overwrites the existing fixture on every call

---

## Definition of Done

- [ ] All 4 agent files use `ConversableAgent`
- [ ] All 4 agent files have `if __name__ == "__main__"` blocks
- [ ] `verifier.py` hardcodes `tool_call_id=None` and `verified_sources_count=0`
- [ ] `action_agent.py` has no approval check
- [ ] `human_gate.py` always returns `approval_status: "pending"`
- [ ] `trace_emitter.py` writes to `zone_b/fixtures/sample_trace.json`
- [ ] Zero imports from `zone_b/`
- [ ] No hardcoded API keys
- [ ] Local git commit after each file, no push
