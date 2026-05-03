# Concord Lite

A contract-to-repair diagnostic layer for AG2 multi-agent workflows.

Concord Lite watches a multi-agent workflow run, detects contract violations (missing evidence, broken tool calls, unapproved side effects), attributes the failure to the responsible agent, generates a repair patch targeting the right AG2 primitive, and validates the fix in a sandboxed regression test — all automatically.

---

## How it works

```
Zone A (target workflow)              Zone B (Concord diagnostic)
─────────────────────────             ───────────────────────────────────────────
ResearcherAgent  (Tavily)             TraceCollector   parse raw trace JSON
      ↓                                     ↓
CriticAgent                           ContractChecker  detect violations (3 rules)
      ↓                                     ↓
VerifierAgent    ← broken             Attribution      identify failed agent + root cause
      ↓                                     ↓
ReporterAgent    ← runs anyway        Repair           suggest fix + AG2 primitive
      ↓                                     ↓
ActionAgent      ← no approval        RegressionTest   generate + run pytest in Daytona
      ↓                                     ↓
trace_emitter                         Reporter         assemble Contract Violation Report
      ↓                                     ↓
zone_b/fixtures/sample_trace.json     HumanGate        auto-approve for demo
```

Zone A is intentionally broken in 3 ways. Zone B is designed to catch all 3.

### 3 intentional failures

| Failure | Contract type | AG2 primitive to fix |
|---|---|---|
| `VerifierAgent` sets `verified_sources_count=0` despite claiming to verify | evidence | Guardrail |
| `VerifierAgent` has `tool_call_id=null` despite claiming tool use | tool | OnContextCondition |
| `ActionAgent` runs before `approval_status=approved` | approval | HumanGate |

---

## Stack

| Tool | Role |
|---|---|
| AG2 (`ag2>=0.12`) | Multi-agent framework — `ConversableAgent`, `GroupChat`, `GroupChatManager` |
| Gemini 2.5 Flash | LLM via OpenRouter (OpenAI-compatible API) |
| Tavily | Web search for ResearcherAgent |
| Daytona | Sandboxed code execution for regression tests |

---

## Project structure

```
shared/
  models.py           all shared dataclasses (both zones import from here)

zone_a/               Literature Review Assistant (target workflow — broken by design)
  config.py
  context_variables.py
  workflow_contract.py
  agents/
    researcher.py     Tavily web search
    critic.py         evidence critique
    verifier.py       BROKEN: tool_call_id=null, verified_sources_count=0
    reporter.py       runs despite unverified sources
    action_agent.py   BROKEN: runs without approval
    human_gate.py     returns pending, never approved
  trace_emitter.py    writes run trace to zone_b/fixtures/sample_trace.json
  run.py              GroupChat entry point

zone_b/               Concord diagnostic pipeline
  config.py           get_llm_config() — single source of truth for LLM config
  fixtures/
    sample_trace.json pre-baked broken run_041 trace for standalone testing
  agents/
    trace_collector.py  parse JSON → RunTrace + ContextSnapshot (no LLM)
    contract_checker.py 3 contract rules, deterministic checks + LLM text
    attribution.py      identify failed agent and root cause
    repair.py           map violation → AG2 primitive, generate patch
    regression_test.py  generate pytest + run in Daytona sandbox
    reporter.py         assemble final ContractViolationReport
    human_gate.py       present proposal, auto-approve for demo
  orchestrator.py     GroupChat wiring all 6 Zone B agents

tests/
  conftest.py
  test_models.py           21 tests — dataclass field integrity
  test_trace_collector.py  35 tests — parsing, folding, edge cases
  test_contract_checker.py 21 tests — contract lambdas + LLM integration

run_all.py            root entry point: Zone A → Zone B → report
concord-lite.html     visual design spec — Contract Violation Report output format
pyproject.toml        editable install, dependency declarations, pytest config
```

---

## Setup

```bash
git clone https://github.com/d3v07/AG2_Hackathon.git
cd AG2_Hackathon
pip install -e .
```

Create `.env` in the repo root:
```
OPENROUTER_API_KEY=your_key
TAVILY_API_KEY=your_key
DAYTONA_API_KEY=your_key
DAYTONA_API_URL=https://app.daytona.io/api
```

---

## Running

**Zone B standalone (Sprint 1 — works now):**
```bash
python3 zone_b/run.py
# Trace: run_041: 5 events, 1 tool call(s), handoff path length 5
# Violations found: 3
#   [HIGH] evidence: verified_sources_count must be > 0 before ReporterAgent runs
#   [HIGH] tool: VerifierAgent must record a tool_call_id
#   [HIGH] approval: ActionAgent requires approval_status == approved
```

**Full pipeline (Sprint 2 — after all Sprint 1 issues merged):**
```bash
python3 run_all.py
```

**Demo output:**
```bash
python3 demo/run_demo.py
```

---

## Tests

```bash
# Fast unit tests only (no API calls, ~0.5s)
pytest tests/ -m "not integration"

# Full suite including LLM integration tests (~20s)
pytest tests/
```

Current status: **77/77 passing**

---

## AG2 patterns

All agents in this repo follow these patterns exactly. PRs that deviate will be rejected.

**Single agent:**
```python
from autogen import ConversableAgent, UserProxyAgent
from zone_b.config import get_llm_config   # or zone_a.config

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

**GroupChat:**
```python
from autogen import GroupChat, GroupChatManager

groupchat = GroupChat(agents=[...], messages=[], max_round=12, speaker_selection_method="round_robin")
manager = GroupChatManager(groupchat=groupchat, llm_config=get_llm_config())
```

Never use `autogen.beta.Agent`. Never use `get_config()`. Always `code_execution_config=False`.

---

## `concord-lite.html`

Visual design spec for the Contract Violation Report output. This was the team's alignment artifact before Sprint 1 — it defines what the final report should look like, what fields it must contain, and how severity and repair confidence should be presented. Open it in a browser to see the target output format. Zone B's `reporter.py` and `demo/run_demo.py` must produce output that matches this shape.

---

## Team

| GitHub | Zone | Sprint 1 issue |
|---|---|---|
| d3v07 | Zone B | #1 — Scaffold + shared models + TraceCollector + ContractChecker |
| Frex22 | Zone B | #2 — Attribution + Repair + RegressionTest + Reporter + Orchestrator |
| PruthviVKadam | Zone A | #3 — Scaffold + ContextVariables + Researcher + Critic |
| niharika2701 | Zone A | #4 — Verifier + Reporter + ActionAgent + HumanGate + Trace Emitter |
