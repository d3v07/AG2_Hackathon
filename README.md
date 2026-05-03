# Concord Lite

**A contract-to-repair diagnostic layer for AG2 multi-agent workflows.**

Concord Lite monitors a multi-agent workflow run, detects when agents violate their behavioural contracts, attributes the root cause to the responsible agent, proposes a repair targeting the correct AG2 primitive, and validates the fix with a sandboxed regression test — all automatically, end-to-end.

> **Live demo:** https://concord-lite.vercel.app/
> **Pipeline (CLI):** `python run_all.py --fixture`
> **Architecture & Q&A doc:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Demo Path (4 minutes)

1. Open the live mission-control dashboard: **https://concord-lite.vercel.app/**
2. Walk the 7 screens:
   - **Overview** — Run #041 stats + animated agent pipeline (▶ REPLAY RUN to play through 12 steps)
   - **Workflow DAG** — declared topology vs observed path, with skipped guards / missing approvals highlighted
   - **Agent Trace** — 12-event timeline with FAIL/WARN flags
   - **Violations** — 4 detected (V-001 evidence, V-002 tool, V-003 routing, V-004 approval). Click a row → jumps to the matching repair patch.
   - **Repair Patch** — 4 AG2-native primitives (Guardrail, ToolGate, OnContextCondition, UserProxyAgent/HumanGate) shown as before/after diffs
   - **Regression** — Daytona sandbox terminal log + 4 PASS assertions
   - **Final Report** — narrative + RERUN READY status flip + APPROVE block
3. Run the backend pipeline locally: `python run_all.py --fixture` (no API keys needed) — produces the same Contract Violation Report on stdout that drives the dashboard.

---

## The Idea

Multi-agent systems fail silently. An agent claims it verified sources but sets `verified_sources_count=0`. Another runs a side-effect action without waiting for human approval. A third records no tool call despite claiming it searched. These are contract violations — the gap between what an agent *says* it did and what it *actually* produced in the trace.

Concord Lite is a diagnostic pipeline that sits *outside* the target workflow, reads its execution trace, and systematically detects, attributes, and repairs those gaps.

```
Zone A: target workflow (broken by design)
         ↓  execution trace (JSON)
Zone B: Concord diagnostic (detects, attributes, repairs)
         ↓  Contract Violation Report
```

---

## Architecture

### Full pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│  python run_all.py  (or --fixture to skip Zone A)                       │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
           ┌───────────────────▼──────────────────────┐
           │              ZONE A                       │
           │      Literature Review Assistant          │
           │         (broken by design)                │
           └───────────────────┬──────────────────────┘
                               │
       task.json ──────────────┤
  (task, research_question,    │
   run_id)                     │
                               ▼
              ┌────────────────────────────┐
              │  ResearcherAgent  [step 1] │──→ Tavily API
              │  tool_call_id = "tc_001"   │    3 sources retrieved
              └──────────────┬─────────────┘
                             │
                             ▼
              ┌────────────────────────────┐
              │    CriticAgent  [step 2]   │    critique notes
              │    tool_call_id = null     │    risk flags
              └──────────────┬─────────────┘
                             │
                             ▼
              ┌────────────────────────────┐
              │   VerifierAgent [step 3]   │  ⚠ INTENTIONALLY BROKEN
              │   tool_call_id = null  ✗   │  ← Contract C2 violation
              │   verified_sources = 0  ✗  │  ← Contract C1 violation
              └──────────────┬─────────────┘
                             │
                             ▼
              ┌────────────────────────────┐
              │  ReporterAgent  [step 4]   │    runs despite 0 verified
              │  produces final_output     │    sources (cascading failure)
              └──────────────┬─────────────┘
                             │
                             ▼
              ┌────────────────────────────┐
              │   HumanGate  [gate]        │  ⚠ INTENTIONALLY BROKEN
              │   approval = "pending"  ✗  │  ← never approves
              └──────────────┬─────────────┘
                             │
                             ▼
              ┌────────────────────────────┐
              │  ActionAgent  [step 5]     │  ⚠ INTENTIONALLY BROKEN
              │  runs without approval  ✗  │  ← Contract C4 violation
              └──────────────┬─────────────┘
                             │
                             ▼
                    trace_emitter.py
            zone_b/fixtures/sample_trace.json
                             │
           ┌─────────────────▼──────────────────────┐
           │              ZONE B                     │
           │        Concord Diagnostic               │
           └─────────────────┬──────────────────────┘
                             │
                             ▼
              ┌────────────────────────────┐
              │  TraceCollector   [B1]     │    JSON → RunTrace
              │  (no LLM)                  │    + ContextSnapshot
              └──────────────┬─────────────┘
                             │
                             ▼
              ┌────────────────────────────┐
              │  ContractChecker  [B2]     │    checks 3 rules
              │  (deterministic + LLM      │    → 3 Violation objects
              │   for human text)          │    all HIGH severity
              └──────────────┬─────────────┘
                             │
                         3 violations
                             │
                             ▼
              ┌────────────────────────────┐
              │  Attribution  [B3]         │──→ LLM
              │                            │    failed_agent = VerifierAgent
              └──────────────┬─────────────┘    failed_step  = 3
                             │
                             ▼
              ┌────────────────────────────┐
              │  Repair  [B4]              │──→ LLM
              │                            │    primitive  = Guardrail
              └──────────────┬─────────────┘    confidence = 0.85
                             │
                             ▼
              ┌────────────────────────────┐
              │  RegressionTest  [B5]      │──→ LLM generates test code
              │                            │──→ Daytona sandbox runs it
              └──────────────┬─────────────┘    status: pass / fail
                             │
                             ▼
              ┌────────────────────────────┐
              │  Reporter  [B6]            │──→ LLM
              │                            │    Contract Violation Report
              └──────────────┬─────────────┘    + narrative
                             │
                             ▼
              ┌────────────────────────────┐
              │  HumanGate  [B7]           │    auto-approves (demo)
              │                            │    approval_status = approved
              └──────────────┬─────────────┘
                             │
                             ▼
        ╔═══════════════════════════════════╗
        ║   CONTRACT VIOLATION REPORT       ║
        ╠═══════════════════════════════════╣
        ║  run_id       : run_041           ║
        ║  violations   : 3  (all HIGH)     ║
        ║  failed_agent : VerifierAgent     ║
        ║  primitive    : Guardrail         ║
        ║  confidence   : 0.85              ║
        ║  regression   : pass / fail       ║
        ║  approval     : approved          ║
        ╚═══════════════════════════════════╝
```

---

## The 3 Intentional Violations

Zone A is deliberately broken in exactly three ways. Zone B must detect all three.

| ID | Contract type | Severity | What breaks | AG2 primitive to fix |
|----|--------------|----------|-------------|----------------------|
| C1 | `evidence` | HIGH | `VerifierAgent` sets `verified_sources_count=0` in `context_delta` — `ReporterAgent` runs with no verified evidence | `Guardrail` |
| C2 | `tool` | HIGH | `VerifierAgent` has `tool_call_id=None` despite claiming to verify sources — no tool use recorded | `OnContextCondition` |
| C3 | `approval` | HIGH | `ActionAgent` runs with `approval_status="pending"` — HumanGate never approves | `HumanGate` |

These failures cascade: C2 prevents C1 from being fixable at runtime, and C3 is independent. Zone B's `ContractChecker` checks each rule deterministically against the `ContextSnapshot`, then uses an LLM to generate human-readable `expected` / `observed` text for each violation.

---

## Shared Data Models

All data flowing between agents — across both zones — is typed via dataclasses in `shared/models.py`. Nothing passes as raw dicts between pipeline stages.

```
ToolEvent
  tool_name    str       "tavily_search"
  input        Any       the query sent
  output       Any       "3 results returned"
  status       str       "success" | "failure"
  evidence_id  str       "ev_001"
  timestamp    float

TraceEvent                         ← one per agent turn in Zone A
  step         int                 1 – 5
  agent        str                 "ResearcherAgent" etc.
  type         str                 "agent_turn"
  content      str                 the agent's text output
  tool_call_id str | None          non-null only for ResearcherAgent
  context_delta dict               incremental state update
  handoff_to   str | None          next agent in chain
  timestamp    float

RunTrace                           ← full Zone A execution record
  run_id       str                 "run_041"
  workflow_name str
  events       list[TraceEvent]
  final_output Any

ContextSnapshot                    ← folded state after all events
  retrieved_sources    list        from ResearcherAgent
  verified_sources_count int       0 (broken by design)
  tool_events          list[ToolEvent]
  approval_status      str         "pending" | "approved" | "rejected"
  failed_agent         str | None
  failed_step          int | None
  final_output         Any

Violation                          ← one per broken contract
  contract_type  str               "evidence" | "tool" | "approval" etc.
  severity       str               "high" | "medium" | "low"
  rule           str
  expected       str               LLM-generated human text
  observed       str               LLM-generated human text
  failed_agent   str
  failed_step    int
```

### How `context_delta` folding works

Each `TraceEvent` carries a `context_delta` — the *incremental* state change that agent produced. `TraceCollector._build_context_snapshot()` folds all deltas left-to-right into a single `ContextSnapshot`:

- **Scalar fields** (`verified_sources_count`, `approval_status`, `final_output`): last write wins
- **`tool_events`**: accumulated (extended, not replaced)
- **Unknown keys** (e.g. `action_event`): silently dropped during `ContextSnapshot` construction

This means Zone A agents only need to emit what *they* changed — not the full state.

---

## Zone A Design

Zone A is the *target workflow* — the system being monitored. It implements a Literature Review Assistant.

### Agent chain

```
task.json
    │
    ├─→ ResearcherAgent   calls Tavily, returns 3 sources + summary
    ├─→ CriticAgent       critiques sources, returns notes + risk flags
    ├─→ VerifierAgent     [BROKEN] returns tool_call_id=None, verified_sources_count=0
    ├─→ ReporterAgent     assembles final_output dict (runs anyway)
    ├─→ HumanGate         [BROKEN] always returns approval_status="pending"
    └─→ ActionAgent       [BROKEN] runs without checking approval_status
```

### Return shape contract

Every Zone A agent must return a dict with exactly these keys — `run.py` converts them to `TraceEvent` via `_to_trace_event()`:

```python
{
    "step":         int,          # 1–5
    "agent":        str,          # agent class name
    "type":         "agent_turn",
    "content":      str,          # agent's primary text output
    "tool_call_id": str | None,   # non-null only when a real tool was called
    "context_delta": dict,        # incremental state — only what this agent changed
    "handoff_to":   str | None,   # next agent name
    "timestamp":    float,        # time.time()
}
```

### `context_delta` keys by agent

| Agent | Keys emitted in `context_delta` |
|-------|--------------------------------|
| ResearcherAgent | `retrieved_sources`, `tool_events` |
| CriticAgent | *(empty)* |
| VerifierAgent | `verified_sources_count` (= 0) |
| ReporterAgent | `final_output` |
| ActionAgent | `action_event` |

### Shared utilities (`zone_a/agents/_utils.py`)

All Zone A agents use:
- `make_proxy(name)` — creates a standard `UserProxyAgent` with `llm_config=False`, `human_input_mode="NEVER"`, `is_termination_msg=lambda x: True`, `max_consecutive_auto_reply=0`, `code_execution_config=False`
- `strip_json_fences(text)` — removes ` ```json ` fences from LLM responses before `json.loads()`

---

## Zone B Design

Zone B is the *diagnostic pipeline* — it never runs Zone A's agents, only reads the trace Zone A emitted.

### Pipeline stages

| Stage | Agent | LLM? | Input | Output |
|-------|-------|------|-------|--------|
| B1 | TraceCollector | No | raw JSON | `RunTrace` + `ContextSnapshot` |
| B2 | ContractChecker | Yes (text only) | `RunTrace` + `ContextSnapshot` | `list[Violation]` |
| B3 | Attribution | Yes | violations + trace | `failed_agent`, `failed_step`, `likely_root_cause` |
| B4 | Repair | Yes | violations + attribution | `affected_primitive`, `patch_code`, `confidence` |
| B5 | RegressionTest | Yes + Daytona | repair patch + violations | `test_status`, `sandbox_id` |
| B6 | Reporter | Yes | all upstream outputs | Contract Violation Report dict |
| B7 | HumanGate | No | report | `approval_status = "approved"` |

### Violation → Primitive mapping (deterministic)

`repair.py` maps violation type to AG2 primitive without an LLM call:

```
evidence  →  Guardrail
tool      →  OnContextCondition
routing   →  Handoff
approval  →  HumanGate
schema    →  Guardrail
```

The LLM is only used to generate `patch_code` and `expected_impact` text for the chosen primitive.

### ContractChecker rules

Three rules, all checked deterministically against `ContextSnapshot`:

```python
# C1 — evidence
lambda trace, snap: snap.verified_sources_count > 0

# C2 — tool
lambda trace, snap: any(
    e.agent == "VerifierAgent" and e.tool_call_id
    for e in trace.events
)

# C3 — approval
lambda trace, snap: snap.approval_status == "approved"
```

The LLM is called *after* a check fails — only to produce `expected` / `observed` strings for the report.

### Shared utilities (`zone_b/utils.py`)

- `make_proxy(name)` — same contract as Zone A's version
- `parse_json_body(body)` — strips ` ```json ` fences and raises `ValueError` on parse failure (not silent)

### RegressionTest + Daytona

`RegressionTest` uses an LLM to generate a self-contained Python script that simulates the post-repair state and asserts each violation is no longer reachable. The script is executed in a fresh Daytona sandbox via `daytona.process.code_run()`. The sandbox is always deleted, even on error. If `DAYTONA_API_KEY` or `DAYTONA_API_URL` are absent, the stage returns `test_status="error"` and `sandbox_id="no-sandbox"` without crashing the pipeline.

---

## Project Structure

```
.
├── run_all.py                      entry point — chains Zone A → Zone B
│
├── shared/
│   └── models.py                   all shared dataclasses (ToolEvent, TraceEvent,
│                                   RunTrace, ContextSnapshot, Violation, ...)
│
├── zone_a/                         Literature Review Assistant (target workflow)
│   ├── config.py                   get_llm_config() — Gemini Flash via OpenRouter
│   ├── context_variables.py        ZoneAContext dataclass
│   ├── workflow_contract.py        C1–C5 contract definitions (reference)
│   ├── trace_emitter.py            writes RunTrace → zone_b/fixtures/sample_trace.json
│   ├── run.py                      pipeline orchestrator + _to_trace_event()
│   ├── fixtures/
│   │   └── task.json               task, research_question, run_id
│   └── agents/
│       ├── _utils.py               make_proxy(), strip_json_fences()
│       ├── researcher.py           Tavily search → sources + summary
│       ├── critic.py               critique notes + risk flags
│       ├── verifier.py             ⚠ BROKEN: tool_call_id=None, verified_sources_count=0
│       ├── reporter.py             final_output dict assembly
│       ├── human_gate.py           ⚠ BROKEN: always returns pending
│       └── action_agent.py         ⚠ BROKEN: runs without approval
│
├── zone_b/                         Concord diagnostic pipeline
│   ├── config.py                   get_llm_config() — same model, same pattern
│   ├── utils.py                    make_proxy(), parse_json_body()
│   ├── orchestrator.py             wires B1–B7 sequentially
│   ├── run.py                      standalone Zone B runner (reads fixture)
│   ├── sandbox_run.py              Daytona demo runner with mock trace
│   ├── fixtures/
│   │   └── sample_trace.json       pre-baked run_041 trace (3 violations)
│   └── agents/
│       ├── trace_collector.py      JSON → RunTrace + ContextSnapshot (no LLM)
│       ├── contract_checker.py     3 rules, deterministic + LLM text
│       ├── attribution.py          LLM → failed_agent + root cause
│       ├── repair.py               primitive map + LLM patch code
│       ├── regression_test.py      LLM test gen + Daytona execution
│       ├── reporter.py             LLM narrative + report assembly
│       └── human_gate.py           auto-approves (demo mode)
│
├── public/                         frontend (Vercel-deployed mission-control dashboard)
│   ├── index.html                  self-contained HTML + inline React app + fixture
│   ├── styles.css                  monospace dark-mode UI tokens
│   ├── app.jsx                     7-screen React component tree (split-file copy)
│   └── data.js                     extracted CONCORD_DATA fixture (split-file copy)
│
├── api/                            backend HTTP layer (FastAPI; not deployed yet)
│   ├── index.py                    routes: /api/health, /api/runs, /api/runs/{id}.js, approval
│   ├── adapter.py                  Zone B report → CONCORD_DATA shape
│   └── store.py                    in-memory run store seeded with RUN-041
│
├── vercel.json                     static-only deploy config
├── requirements.txt                FastAPI deps (for the api/ layer)
│
└── tests/
    ├── conftest.py                 shared fixtures (sample_trace_raw, clean_trace_raw, ...)
    ├── test_models.py              21  — dataclass field integrity
    ├── test_trace_collector.py     35  — parsing, folding, snapshot building
    ├── test_contract_checker.py    17  — contract lambdas + step lookup
    ├── test_attribution.py         10  — deterministic fallback paths
    ├── test_repair.py              15  — _pick_primary, PRIMITIVE_MAP, patch gen
    ├── test_regression_test.py     16  — _parse_status, fallback test execution
    ├── test_reporter.py            13  — report assembly, severity summary
    ├── test_human_gate.py           6  — approval output shape
    ├── test_zone_a.py              22  — strip_json_fences, _to_trace_event, agent shapes
    ├── test_integration.py         14  — Zone A→B schema, 3 violations, clean trace = 0
    └── test_rigorous.py            57  — edge cases, error paths, boundary conditions
                                   ────
                                   226  total (223 unit + 13 integration-marked)
```

---

## Setup

```bash
git clone https://github.com/d3v07/AG2_Hackathon.git
cd AG2_Hackathon
pip install -e .
```

Create `.env` in the repo root:

```env
OPENROUTER_API_KEY=your_openrouter_key
TAVILY_API_KEY=your_tavily_key
DAYTONA_API_KEY=your_daytona_key
DAYTONA_API_URL=https://app.daytona.io/api
```

Only `OPENROUTER_API_KEY` is required to run Zone B. `TAVILY_API_KEY` is required to run Zone A live. `DAYTONA_*` is required only for the sandboxed regression test stage.

---

## Running

### Fixture mode — no API keys needed for Zone A

Uses the pre-baked `zone_b/fixtures/sample_trace.json` (run_041, 3 violations). Runs the full Zone B diagnostic pipeline live with your LLM keys.

```bash
python run_all.py --fixture
```

### Full live run — all keys required

Runs Zone A end-to-end (Tavily search → agent chain → trace emission), then runs Zone B on the freshly generated trace.

```bash
python run_all.py
```

### Zone B standalone

```bash
python zone_b/run.py
```

### Zone A standalone

```bash
python zone_a/run.py
```

### Expected output (fixture mode)

```
============================================================
  CONCORD LITE — Full Pipeline Run
============================================================

[Zone A] Skipped — using fixture trace
  Trace loaded from zone_b/fixtures/sample_trace.json

[Zone B] Running diagnostic pipeline...
[1/7] TraceCollector — loading zone_b/fixtures/sample_trace.json
      run_041: 5 events, 1 tool call(s), handoff path length 5
[2/7] ContractChecker — applying contracts
      3 violation(s) found
[3/7] Attribution — identifying failed agent
      failed_agent=VerifierAgent step=3
[4/7] Repair — mapping to AG2 primitive
      affected_primitive=Guardrail confidence=0.85
[5/7] RegressionTest — running in Daytona
      test_status=pass sandbox=<id>
[6/7] Reporter — assembling Contract Violation Report
[7/7] HumanGate — approval check
      Decision: APPROVED

============================================================
  CONTRACT VIOLATION REPORT
============================================================
  Run ID            : run_041
  Violations        : 3
  Severity          : {'high': 3, 'medium': 0, 'low': 0}
  Failed agent      : VerifierAgent (step 3)
  Root cause        : VerifierAgent failed to use a tool to gather verified sources
  Affected primitive: Guardrail
  Repair confidence : 0.85
  Approval status   : approved
============================================================
```

---

## Tests

```bash
# Fast — no API calls (~0.5s, 223 tests)
pytest tests/ -m "not integration"

# Full suite including LLM + Daytona integration tests
pytest tests/
```

### What's tested

| File | Count | What it covers |
|------|-------|----------------|
| `test_models.py` | 21 | All shared dataclasses, field types, optional fields |
| `test_trace_collector.py` | 35 | JSON parsing, context_delta folding, edge cases |
| `test_contract_checker.py` | 17 | All 3 contract lambdas, boundary values, step lookup |
| `test_attribution.py` | 10 | Deterministic fallback, empty violations |
| `test_repair.py` | 15 | `_pick_primary` severity ranking, full `PRIMITIVE_MAP` coverage |
| `test_regression_test.py` | 16 | `_parse_status` edge cases, fallback test code executes PASS |
| `test_reporter.py` | 13 | Report assembly, severity summary, fallback narrative |
| `test_human_gate.py` | 6 | Auto-approve shape, handles empty report |
| `test_zone_a.py` | 22 | `strip_json_fences`, `_to_trace_event`, all 5 agent return shapes |
| `test_integration.py` | 14 | Zone A→B schema compatibility, exactly 3 violations, clean trace = 0 |
| `test_rigorous.py` | 57 | Edge cases, error paths, partial violations, data-flow contracts |

---

## AG2 Patterns — Design Guide

All agents in this codebase follow these patterns. PRs that deviate will be rejected.

### Standard single-turn agent

```python
from autogen import ConversableAgent
from zone_b.config import get_llm_config   # or zone_a.config
from zone_b.utils import make_proxy        # or zone_a.agents._utils

agent = ConversableAgent(
    name="AgentName",
    llm_config=get_llm_config(),
    system_message="...",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=1,
    code_execution_config=False,           # always False
)
proxy = make_proxy("AgentNameProxy")       # shared helper, never inline

result = proxy.initiate_chat(agent, message="...", max_turns=1)
output = result.chat_history[-1]["content"]
```

### Parsing LLM JSON responses

Never trust LLMs to return bare JSON. Always strip fences first:

```python
# Zone A
from zone_a.agents._utils import strip_json_fences
parsed = json.loads(strip_json_fences(result.chat_history[-1]["content"]))

# Zone B
from zone_b.utils import parse_json_body
parsed = parse_json_body(result.chat_history[-1]["content"])  # raises ValueError on failure
```

### LLM config

Both zones use the same `get_llm_config()` pattern — Gemini 2.5 Flash via OpenRouter, temperature 0.1:

```python
def get_llm_config(model: str = "google/gemini-2.5-flash") -> dict:
    return {
        "config_list": [{
            "model": model,
            "api_key": os.environ["OPENROUTER_API_KEY"],
            "base_url": "https://openrouter.ai/api/v1",
            "api_type": "openai",
        }],
        "temperature": 0.1,
    }
```

### Rules

- Never use `autogen.beta.Agent`
- Never call `get_config()` — use `get_llm_config()` from the zone's `config.py`
- Always set `code_execution_config=False` on both agent and proxy
- Always set `human_input_mode="NEVER"` on both
- `max_consecutive_auto_reply=1` on agents, `0` on proxies
- Use `make_proxy()` — never copy-paste the 8-line `UserProxyAgent` block
- Validate JSON parsing at the boundary — never `json.loads()` raw LLM output

---

## Stack

| Tool | Version | Role |
|------|---------|------|
| [AG2](https://github.com/ag2ai/ag2) | `>=0.12` | Multi-agent framework — `ConversableAgent`, `UserProxyAgent` |
| Gemini 2.5 Flash | — | LLM for all agents, via OpenRouter |
| [OpenRouter](https://openrouter.ai) | — | OpenAI-compatible API proxy for Gemini |
| [Tavily](https://tavily.com) | — | Web search API for ResearcherAgent |
| [Daytona](https://daytona.io) | — | Sandboxed code execution for regression tests |
| Python | `>=3.12` | Required for `str | None` type unions |

---

## Team

| GitHub | Zone | Sprint 1 | Sprint 2 |
|--------|------|----------|----------|
| [d3v07](https://github.com/d3v07) | Zone B | #1 — Scaffold + models + TraceCollector + ContractChecker | #5 — Wire Zone A→B + run_all.py |
| [Frex22](https://github.com/Frex22) | Zone B | #2 — Attribution + Repair + RegressionTest + Reporter + Orchestrator | #6 — Zone B full pytest suite + Daytona tests |
| [PruthviVKadam](https://github.com/PruthviVKadam) | Zone A | #3 — Scaffold + ContextVariables + ResearcherAgent + CriticAgent | #7 — Zone A live run + trace schema validation |
| [niharika2701](https://github.com/niharika2701) | Zone A | #4 — VerifierAgent + ReporterAgent + ActionAgent + HumanGate + trace_emitter | #8 — Contract Violation Report validation + demo run |
