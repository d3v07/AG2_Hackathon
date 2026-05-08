# Concord Lite — Architecture & Demo Walkthrough

**Live demo:** https://concord-lite.vercel.app/
**Repo:** https://github.com/d3v07/AG2_Hackathon
**Built with:** AG2 (autogen) · Tavily · Daytona · Gemini 2.5 Flash via OpenRouter

This doc is the Q&A-ready reference. Read it, keep it open during the demo. Every claim here is grounded in the actual code paths cited inline.

---

## 1. The Pitch (30 seconds)

Multi-agent systems fail silently. An agent claims "I verified the sources" but writes `verified_sources_count=0`. An action agent saves a report without waiting for human approval. A reporter emits final output before the verifier even ran a tool call. These are **contract violations** — the gap between what an agent *says* and what its trace *proves*.

**Concord Lite is a 7-agent diagnostic pipeline that watches a multi-agent workflow run, detects every contract violation in the trace, attributes it to the responsible agent, generates an AG2-native repair patch, validates the patch in a sandboxed pytest, and produces a Contract Violation Report — fully automated.**

We didn't build a better workflow. We built a *referee* for any AG2 workflow.

---

## 2. Two Zones

```
┌──────────────────────────────────────────────────────────────────────┐
│  Zone A — TARGET WORKFLOW (Literature Review Assistant)             │
│  Broken by design. Demonstrates the contract violations Zone B      │
│  catches. Produces a JSON trace.                                     │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │  zone_b/fixtures/sample_trace.json
┌────────────────────────────────▼─────────────────────────────────────┐
│  Zone B — CONCORD DIAGNOSTIC                                         │
│  7 agents in a deterministic pipeline. Reads the trace, detects     │
│  violations, attributes blame, generates a repair, runs the repair  │
│  in Daytona, assembles the final report, gates on human approval.   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │  Contract Violation Report (dict)
                                 ▼
                  Frontend mission-control dashboard
                  (concord-lite.vercel.app)
```

**Key separation:** Zone B does NOT depend on the specific Zone A workflow. Point Zone B at any AG2 trace JSON with the right shape (`shared/models.py`) and it produces a report. Zone A is just a demo target.

---

## 3. Zone A — The Broken Workflow (`zone_a/`)

**Domain:** Literature review on whether multi-agent systems improve research-workflow reliability.

**Five agents, sequential, all `ConversableAgent` instances** (`zone_a/run.py:44-95`):

| Step | Agent | What it does | AG2 primitive | External tool | Status |
|------|-------|--------------|---------------|---------------|--------|
| 1 | `ResearcherAgent` | Calls **Tavily** search for the research question, asks LLM to format the JSON envelope | `ConversableAgent` + `UserProxyAgent` proxy, `initiate_chat(max_turns=1)` | **Tavily** `client.search(query, max_results=3)` | works |
| 2 | `CriticAgent` | Reviews sources, emits critique notes | `ConversableAgent` | none | works |
| 3 | `VerifierAgent` | **Intentionally broken** — claims to verify but emits `tool_call_id=None` and `verified_sources_count=0` | `ConversableAgent` | none | **broken** |
| 4 | `ReporterAgent` | Assembles `final_output` despite unverified sources | `ConversableAgent` | none | broken-by-association |
| 5 | `ActionAgent` | "Saves" the report — runs without `approval_status=='approved'` | `ConversableAgent` | none | **broken** |

**Where the failures are baked in (so Zone B has something to catch):**
- `zone_a/agents/verifier.py:36-37` → `tool_call_id=None`, `context_delta={"verified_sources_count": 0}`
- `zone_a/agents/human_gate.py:65` → returns `{"approval_status": "pending"}` by default
- `zone_a/agents/action_agent.py` → runs the side-effect regardless

**Output:** `zone_b/fixtures/sample_trace.json` — a normalised `RunTrace` written by `zone_a/trace_emitter.py`.

---

## 4. Zone B — The Concord Diagnostic Pipeline (`zone_b/`)

Seven agents, sequential, deterministic data flow. Each agent has a typed input and typed output. The orchestrator (`zone_b/orchestrator.py:22-90`) wires them in dependency order.

> **Why sequential not GroupChat:** Diagnostic data flow is a directed acyclic graph — each step's output is the next step's input. A round-robin GroupChat would just add LLM-driven routing on top of an already-deterministic pipeline. We could shim a GroupChat *façade* over this pipeline for chat-style demos, but the underlying flow is what the issue spec requires.

```
TraceCollector → ContractChecker → Attribution → Repair
                                                     ↓
                                             RegressionTest (Daytona)
                                                     ↓
                                                 Reporter → HumanGate
```

### B1. TraceCollector (`zone_b/agents/trace_collector.py`)

- **Input:** raw trace JSON
- **Output:** `RunTrace` + `ContextSnapshot` + handoff path + tool events + summary
- **No LLM.** Pure parsing.
- **Key trick — context folding** (`_build_context_snapshot:43-69`): walks every `TraceEvent.context_delta` left-to-right; `tool_events` is appended (list extension); everything else is overwritten last-write-wins. This collapses the per-event deltas into a single final state — that's the snapshot Zone B reasons over.

### B2. ContractChecker (`zone_b/agents/contract_checker.py`)

- **Input:** `RunTrace` + `ContextSnapshot`
- **Output:** `list[Violation]` + `violation_count` + `severity_summary`
- **Three contracts (deterministic lambdas, lines 9-33):**

  | Contract type | Severity | Rule | Check |
  |---------------|----------|------|-------|
  | `evidence` | high | `verified_sources_count > 0` before Reporter runs | `snap.verified_sources_count > 0` |
  | `tool` | high | VerifierAgent must record a `tool_call_id` (Tavily or Daytona) | any VerifierAgent event has tool_call_id |
  | `approval` | high | ActionAgent requires `approval_status=='approved'` | `snap.approval_status == "approved"` |

- **LLM use:** `ConversableAgent` only generates the human-readable `expected` / `observed` strings (`_generate_violation_text:43-70`). The pass/fail decision is pure code — never delegated to the LLM.

### B3. Attribution (`zone_b/agents/attribution.py`)

- **Input:** violations + trace + snapshot
- **Output:** `failed_agent`, `failed_step`, `likely_root_cause`, `attributions[]`
- **LLM use:** single `ConversableAgent` reasoning over the handoff path + violation metadata, returns JSON.
- **Deterministic fallback (`_deterministic_failed_step:17-21`):** if the LLM response is unparseable, attribution defaults to the first violation's `failed_agent` and the first event matching that agent.
- This is the "blame the right agent" step, separated from the contract checker because the agent who *triggered* a downstream violation is often not the same as the one whose contract failed.

### B4. Repair (`zone_b/agents/repair.py`)

- **Input:** violations + `failed_agent` + `failed_step`
- **Output:** `patches[]` with one repair entry per violation, plus legacy scalar aliases (`repair_patch`, `affected_primitive`, `patch_code`, `expected_impact`, `confidence`) for current callers.
- **Deterministic primitive map (`PRIMITIVE_MAP:15-21`):**

  | Violation type | AG2 primitive |
  |----------------|---------------|
  | `evidence` | **Guardrail** |
  | `tool` | **OnContextCondition** |
  | `routing` | **Handoff** |
  | `approval` | **HumanGate** (UserProxyAgent) |
  | `schema` | **Guardrail** |

- **LLM use:** generates the Python `patch_code` snippet + `expected_impact` sentence for each patch. Falls back to a stub comment per patch if parse fails (`_build_patch`). Confidence drops from 0.85 to 0.5 on fallback.
- `_pick_primary` now selects the highest-severity patch only for legacy scalar aliases; `patches[]` preserves violation input order and cardinality.

### B5. RegressionTest (`zone_b/agents/regression_test.py`) — **Daytona-powered**

- **Input:** `repair_patch` + violations + run trace
- **Output:** `test_name`, `test_code`, `assertions`, `test_status` (pass/fail/error), `stdout`, `sandbox_id`, `duration_ms`, `usage`, `cost`, `per_violation_results[]`, `per_violation_summary`
- **Two-step:**
  1. `_ask_llm_for_test:19-57` — `ConversableAgent` writes a self-contained Python script that simulates post-repair state and asserts each violation is no longer reachable. Script must print `PASS` or `FAIL: <reason>`. Standard library only.
  2. `_run_in_daytona` delegates to `zone_b.sandbox.run_python_in_daytona`, which uses AG2's `autogen.coding.DaytonaCodeExecutor` through a warm `DaytonaExecutorPool`, executes the test with `execute_code_blocks`, parses stdout, and records Daytona duration/cost. After each execution the pool calls `restart()` before reuse, so generated test code gets a clean sandbox state while keeping the next executor warm.
- **Hand-rolled fallback** (`_fallback_test:60-81`): if the LLM call or parse fails, we use a known-good test that asserts the four enforced contracts directly. Means the demo never breaks just because the LLM had a bad turn.
- `_parse_status:82-88` is intentionally strict: needs `PASS` and not `FAIL` to count as pass. Anything else is `error`.

### B6. Reporter (`zone_b/agents/reporter.py`)

- **Input:** trace + violations + attribution + repair + regression result + snapshot
- **Output:** `report` dict with 14+ fields including the violation list, severity summary, repair details, per-violation regression status, and a human-readable `narrative`
- **LLM use:** narrative only (`_ask_llm_for_narrative`). Every other field is direct dict assembly.
- Falls back to a templated narrative on LLM failure.

### B7. HumanGate (`zone_b/agents/human_gate.py`)

- **Input:** the assembled report
- **Output:** `approval_status` + `comments`
- **Two modes:**
  - Default (demo): auto-approves so the pipeline completes end-to-end without operator intervention.
  - `interactive=True`: spawns a real **`UserProxyAgent` with `human_input_mode="ALWAYS"`** that prompts the operator on stdin (lines 27-38). Same AG2 primitive Zone A's swarm uses.

---

## 5. AG2 Patterns in This Code

We use AG2 deliberately, not as a library skin over LLM calls. Specific primitives:

- **`ConversableAgent`** — every reasoning agent. Configured `human_input_mode="NEVER"`, `max_consecutive_auto_reply=1`, `code_execution_config=False`.
- **`UserProxyAgent`** — every agent has a paired proxy via `make_proxy()` (`zone_a/agents/_utils.py`, `zone_b/utils.py`). Single-turn `proxy.initiate_chat(agent, message=..., max_turns=1)` is our standard call.
- **Real `UserProxyAgent` with `human_input_mode="ALWAYS"`** in `zone_b/agents/human_gate.py:32-38` for live human approval. This is the same primitive the repair patch *recommends* for Zone A's broken `ActionAgent` (P-004 in the dashboard).
- **`ContextSnapshot`** modelling — we treat AG2 context as an event-sourced state by folding `context_delta` left-to-right. This mirrors how AG2's own `ContextVariables` works in swarm pattern.
- **Repair targets the AG2 primitive layer**, not user code. When Concord proposes "Guardrail on ReporterAgent" or "OnContextCondition before handoff", those are AG2 framework primitives — the operator can paste the patch into their `ConversableAgent(...)` constructor or `Handoffs(...)` call directly.

**LLM provider:** Gemini 2.5 Flash via OpenRouter, openai-compatible base URL (`zone_a/config.py:7-17`, same in `zone_b/config.py`). Temperature 0.1 — we want deterministic-ish reasoning, not creative writing.

---

## 6. The Three Integrations

### Tavily — real web search in Zone A
- Where: `zone_a/agents/researcher.py:46-58`
- How: `TavilyClient(api_key=os.environ["TAVILY_API_KEY"]).search(query=research_question, max_results=3, search_depth="basic")`
- Why: gives the workflow real-world content to reason over, makes the demo non-trivial. The Tavily call always succeeds; what fails is the downstream `VerifierAgent`'s self-report about whether it used the result.
- Records a `ToolEvent(tool_name="tavily_search", evidence_id="ev_001", status="success")` in the context delta — this is exactly the kind of evidence the `tool` contract requires.

### Daytona — sandboxed regression testing in Zone B
- Where: `zone_b/agents/regression_test.py:91-117`
- How: spin a fresh Linux sandbox per run, exec the LLM-generated test via `sandbox.process.code_run(test_code)`, capture stdout, `daytona.delete(sandbox)` in `finally`.
- Why: we generate code with an LLM and execute it. Doing that on the operator's machine is unsafe. Daytona gives us per-run isolation, no install drift, no cleanup burden, and fast cold starts.
- Demo-friendly: `python zone_b/sandbox_run.py` runs the full Zone B pipeline against a mock Tavily-enriched trace inside Daytona — the sandbox script itself is what gets exec'd.

### OpenRouter / Gemini 2.5 Flash — LLM backbone
- Where: `zone_a/config.py` and `zone_b/config.py`
- Why Gemini Flash: cheap, fast, good enough for structured-JSON tasks. We're parsing every response, not generating prose.
- Why OpenRouter: one API key, model swap is a one-line change, future-proof if Gemini gets deprecated mid-demo.

---

## 7. The 7 Frontend Screens — What They Show & Where the Data Comes From

The frontend is a self-contained React app served as static assets from Vercel (`public/index.html`). All seven screens default to the inlined `window.CONCORD_DATA` fixture, and local API mode can switch to live data through `GET /api/runs/{run_id}` plus a short-lived stream token for `GET /api/runs/{run_id}/events`.

> **Honest framing for Q&A:** The deployed demo still opens in fixture mode for stage reliability. The local FastAPI app serves the same dashboard with a FIXTURE/LIVE toggle; LIVE fetches the persisted run payload and subscribes to the run's SSE lifecycle stream.

### Screen 1 — **Overview** (`screen === "overview"`)
- **Renders:** run metadata strip, 3 stat blocks (4 violations / 5 agents run / 4 patches ready), animated 5-node pipeline graph with REPLAY/PLAY/END STATE controls, contract status table (1/5 passing), run task card.
- **Data sources:** `D.run`, `D.stats`, `D.agents`, `D.contracts`, `D.trace`.
- **Backend equivalent:** Zone B `report.run_id`, `report.violation_count`, `report.severity_summary`, derived per-agent rollups.
- **Interactivity:** clicking any pipeline node navigates to **Agent Trace**. Replay button steps through 12 events at ~520ms/step.

### Screen 2 — **Workflow DAG** (`screen === "topology"`)
- **Renders:** declared-vs-observed graph. Fixture mode shows the full demo topology; live mode renders the observed agents, tools, handoffs, and route status derived from the run trace. Edges are colored by status: OK (sage), SKIPPED GUARD (orange), MISSING APPROVAL (brick), PROPOSED (gold dashed). Below the graph: routes table showing every observed edge and its status.
- **Data sources:** `D.topology.{nodes, edges}`, `D.routes`.
- **Backend equivalent:** `api/adapter.py` derives live `topology` and `routes` from `RunTrace.events`, then annotates observed nodes/routes with violation contract IDs. It does not synthesize fixture nodes for arbitrary live runs.
- **Why this screen matters:** routing violations are *structural* (handoff fired without satisfying a condition). Showing the topology with the broken edge highlighted makes the violation legible at a glance.

### Screen 3 — **Agent Trace** (`screen === "trace"`)
- **Renders:** 12-row event timeline with step / timestamp / agent / event type / context / status / contract flag.
- **Data sources:** `D.trace[]`.
- **Backend equivalent:** `run_trace.events` — exactly what TraceCollector parses (`zone_b/agents/trace_collector.py:21-40`). The frontend's `flag` field maps to `Violation.contract_type`.

### Screen 4 — **Violations** (`screen === "violations"`)
- **Renders:** 4 severity-bar rows (V-001..V-004), each with title, expected, observed, evidence chain, and severity (HIGH/MED). Below: an evidence chain table.
- **Data sources:** `D.violations[]`.
- **Backend equivalent:** `Violation` dataclass (`shared/models.py:51-58`). Each row is one element of `report.violations`.
- **Interactivity:** clicking any violation row navigates to **Repair Patch** with the matching patch pre-selected.

### Screen 5 — **Repair Patch** (`screen === "repair"`)
- **Renders:** 4 patch cards with primitive (Guardrail / ToolGate / OnContextCondition / HumanGate), target agent, before/after diff (red removed lines / green added lines), and an APPLY button per patch. Filter buttons (ALL / P-001 / P-002 / P-003 / P-004).
- **Data sources:** `D.patches[]`.
- **Backend equivalent:** `report.patches[]` from `zone_b/agents/repair.py`, plus scalar `report.affected_primitive` and `report.patch_code` aliases for current callers. The public dashboard adapter still synthesizes the visual diff rows until #17 wires the plural backend output through.

### Screen 6 — **Regression Test** (`screen === "regression"`)
- **Renders:** Daytona terminal stream (every line of the sandbox stdout), sandbox metadata card (sandbox_id, image, runner, duration, status), assertions table (4 PASS rows).
- **Data sources:** `D.test.{sandbox_id, lines, assertions}`.
- **Backend equivalent:** `regression_test.run_regression_test()` returns `{test_name, test_code, assertions, test_status, stdout, sandbox_id, per_violation_results[], per_violation_summary}` — directly maps. The terminal `lines[]` are the captured stdout split per line; assertions come from the LLM's structured response or fallback.
- **Why Daytona shows up here:** this is where it earns its keep. Per-run sandbox, isolated exec, deterministic cleanup.

### Screen 7 — **Final Report** (`screen === "report"`)
- **Renders:** executive summary paragraph, approval block (status PENDING_OPERATOR in orange — flips to APPROVED when the user clicks the approve button), patches-applied table, verification card with EXPORT JSON / VIEW TEST buttons.
- **Data sources:** `D.report.{summary, patches_applied, approval}`.
- **Backend equivalent:** `report.narrative` + `report.approval_status`.
- **Status cluster top-right flips from "4 VIOLATIONS DETECTED" (brick) to "RERUN READY" (sage)** only on this screen — explicit visual signal that the loop is closed.

---

## 8. Data Shape Reference

```
Zone B Report (backend output, shared/models.py + zone_b/agents/reporter.py)
├── run_id                    str
├── workflow_name             str
├── violation_count           int
├── severity_summary          {high, medium, low}
├── failed_agent              str
├── failed_step               int
├── likely_root_cause         str
├── repair_patch              str          (1-line description)
├── affected_primitive        str          (Guardrail / OnContextCondition / etc)
├── patch_code                str          (Python snippet from LLM)
├── patches                   list[dict]   (one repair patch per violation)
├── regression_test_status    str          (pass / fail / error)
├── regression_tests          list[dict]   (one regression result per violation)
├── regression_summary        {pass, fail, error}
├── repair_confidence         float        (0.85 nominal, 0.5 fallback)
├── approval_status           str          (pending / approved / rejected)
├── violations                list[dict]
└── narrative                 str          (LLM-generated)

Frontend CONCORD_DATA (rendered shape, public/index.html inline)
├── run         {id, workflow, started, duration_ms, operator, pattern, manager, task}
├── stats       {violations, agents_run, repair_ready, contracts_total, contracts_passed,
│                events_total, tool_events}
├── agents[]    {id, name, steps, status, note}
├── topology    {entry, nodes[], edges[]}
├── routes[]    {id, from, to, declared, observed, status, contract?, note?}
├── contracts[] {id, type, rule, status}
├── trace[]     {step, ts, agent, type, ctx, status, flag?}
├── violations[]{id, severity, contract, type, title, expected, observed,
│                failed_agent, failed_step, evidence[]}
├── patches[]   {id, violation, primitive, target, title, removed[], added[]}
├── test        {name, runner, sandbox_id, image, duration_ms, lines[], assertions[]}
└── report      {summary, patches_applied[], approval{status, operator, requested_at, sla}}
```

The `api/adapter.py` module does the conversion: `report_to_concord_data(report, run_trace_dict, violations) → CONCORD_DATA`. It synthesises the per-agent rollup from the trace, derives stats, passes native `report.patches[]` through when present, and builds observed topology/routes from the trace.

---

## 9. How to Run It

```bash
# Backend pipeline (no API keys needed for fixture mode)
python run_all.py --fixture

# Backend live run (Tavily search + LLM + Daytona)
export TAVILY_API_KEY=...
export OPENROUTER_API_KEY=...
export DAYTONA_API_KEY=...
export DAYTONA_API_URL=...
python run_all.py

# Frontend (already deployed, but for local dev)
.venv/bin/uvicorn api.index:app --port 8765
# → http://localhost:8765 serves the dashboard via the FastAPI app
#   plus /api/runs/RUN-041 returns the same CONCORD_DATA shape
#   /api/runs/RUN-041/events/token issues a short-lived stream token
#   and /api/runs/RUN-041/events streams status lifecycle events.
```

The 298-test pytest suite covers parsing, contract lambdas, primitive map, fallback paths, per-violation regression status, and Zone A→B integration.

---

## 10. Q&A — Likely Judge Questions

**Q: Why not let the LLM decide if a contract is violated?**
Because contract violations need to be *deterministic*. If the same trace produces a different violation count on different runs, you can't trust the report. The lambdas in `contract_checker.py:9-88` are pure code; the LLM is only used for the human-readable `expected` / `observed` strings.

**Q: Why a separate Attribution agent? Doesn't the contract already name the failed agent?**
Yes for simple cases. But the agent whose contract *failed* is often downstream of the agent who *caused* the failure. Example: Reporter emits final output without verified sources — Reporter's contract failed, but Verifier is responsible for `verified_sources_count=0`. Attribution reasons over the handoff path to surface the upstream cause.

**Q: Why keep scalar repair fields if repairs are per violation?**
Current callers still read `repair_patch`, `affected_primitive`, `patch_code`, and `confidence`. The backend now emits `patches[]` in violation order, while the scalar fields mirror the highest-severity patch until downstream API and dashboard code finish moving to the plural shape.

**Q: What happens if the LLM returns invalid JSON?**
Every Zone B agent has a deterministic fallback path — see `run_attribution:96-114`, `run_repair:97-102`, `_fallback_test:60-79`, `reporter._ask_llm_for_narrative`'s except clause. We never crash because the LLM had a bad turn. We mark `confidence=0.5` instead of `0.85` so the operator knows.

**Q: Why Daytona instead of just running the test locally / in a thread?**
LLM-generated code execution is inherently untrusted. Daytona gives per-run sandboxing with deterministic cleanup (`finally: daytona.delete(sandbox)`). Also, the sandbox image is reproducible — the repair test runs in the same `python:3.11-slim` every time, regardless of what's installed on the operator's machine.

**Q: Is the dashboard wired to the backend?**
Locally yes. The dashboard defaults to fixture mode, but the LIVE toggle fetches `GET /api/runs/{run_id}`, obtains a stream token from `POST /api/runs/{run_id}/events/token`, and listens to `GET /api/runs/{run_id}/events?stream_token=...`. The live deploy can still remain fixture-first for demo reliability.

**Q: What AG2 primitives would a real-world operator install based on this report?**
Exactly the four shown on the Repair Patch screen:
1. **`Guardrail`** on ReporterAgent — `condition=lambda ctx: ctx["verified_sources_count"] > 0`
2. **`OnContextCondition`** on the Verifier→Reporter handoff — gates on a successful tool event
3. **`Handoff` with `forbidden_path`** to prevent skipping the verifier loop
4. **`UserProxyAgent` (HumanGate)** before ActionAgent — `human_input_mode="ALWAYS"`, `is_termination_msg=lambda m: m.get("approval_status")=="approved"`

These are AG2 framework primitives — they paste directly into the operator's existing workflow code.

**Q: How would you extend this beyond Literature Review?**
Zone B reads any trace JSON matching `shared/models.py`. Define your own contracts as lambdas in `CONTRACTS = [...]` and your own primitive map. The architecture is workflow-agnostic — Zone A is just our demo target.

**Q: Track classification — why "Multi-Agent Collaboration" vs "Open"?**
This is a multi-agent observability + repair system. Both tracks fit. Concord is meta — it observes and repairs other multi-agent collaborations. Frame it however the judges respond best to.

---

## 11. What's Honest to Concede

- **The dashboard's per-violation patch diffs are still template-driven** in the fixture. The backend now emits one repair entry per violation in `report.patches[]`, but the public dashboard adapter still synthesizes its visual diff rows until the API passthrough work lands.
- **The topology/routes block on the Workflow DAG screen is not yet derived from a real workflow declaration.** It's a fixture today. Real implementation would parse the operator's AG2 program (or a YAML manifest) to get the declared topology.
- **We use Daytona as a real, live integration**, not a stub. `_run_in_daytona` calls the AG2 `DaytonaCodeExecutor` runner. Without `DAYTONA_API_KEY`/`DAYTONA_API_URL` it returns `("Daytona credentials missing", "no-sandbox", "error")` — not a fake `pass`.
- **Tavily is also live.** `zone_a/agents/researcher.py` actually hits `client.search(...)` for every Zone A run.
- **Live LLM is Gemini 2.5 Flash.** Not local, not stubbed.
