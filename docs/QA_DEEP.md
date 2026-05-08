# Concord Lite — Deep Q&A Reference

Pairs with [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md). This one is for the harder questions — what's used where, how the integrations actually work, why the architecture is shaped this way.

Every claim cites a file:line. If a judge pushes, open the file.

---

# Section 1 — AG2 PRIMITIVES (which one, where, why)

### Q1: Which AG2 primitives does this project actually use?

We use **two execution modes**, both AG2-native:

**Mode A — Sequential pipeline** (`zone_a/run.py`, `zone_b/orchestrator.py`)
- `ConversableAgent` for every reasoning agent
- `UserProxyAgent` paired with each agent (proxy pattern via `make_proxy()` in `zone_a/agents/_utils.py:4-12` and `zone_b/utils.py`)
- `proxy.initiate_chat(agent, message=..., max_turns=1)` — single-turn conversation per agent
- `UserProxyAgent` with `human_input_mode="ALWAYS"` for live human approval (`zone_b/agents/human_gate.py:32-38`, `zone_a/agents/human_gate.py:27-33`)

**Mode B — True AG2 Swarm** (`zone_a/swarm.py`, `zone_b/group_chat.py`)
- `RoundRobinPattern` from `autogen.agentchat.group.patterns`
- `ContextVariables` for shared cross-agent state
- `OnContextCondition` + `StringContextCondition` for **declarative routing rules** (`zone_a/swarm.py:201-219`)
- `RegexGuardrail` for content-level enforcement (`zone_a/swarm.py:221-231`)
- `AgentTarget` and `TerminateTarget` as handoff destinations
- `register_for_llm()` to bind tool functions to agents (`zone_a/swarm.py:181-199`)
- `register_handoffs()` to wire routing
- `register_output_guardrail()` to attach guardrails
- `a_initiate_group_chat()` to run the async swarm
- `ReplyResult` returned from every tool function (`zone_a/swarm_tools.py:23-26`)

### Q2: So which mode does the demo actually run?

Demo runs **Mode A (sequential)** because it's deterministic, fast, and doesn't depend on the LLM choosing the right tool. **Mode B exists, is fully wired, and is invoked via `python run_all.py --swarm`** — that's the version where AG2's swarm primitives literally enforce the contracts at runtime.

### Q3: How is `OnContextCondition` actually used to enforce contracts?

In `zone_a/swarm.py:201-219`. The verifier registers two handoffs:

```python
verifier.register_handoffs([
    OnContextCondition(
        target=AgentTarget(agent=reporter),
        condition=StringContextCondition(variable_name="sources_verified"),
    ),
    OnContextCondition(target=TerminateTarget(), condition=None),
])
```

Translation: "Hand off to Reporter only if `sources_verified` is True; otherwise terminate the swarm." The `sources_verified` variable is set by `record_verification` (`zone_a/swarm_tools.py:43-64`) based on `verified_sources_count > 0 and bool(tool_call_id)`. **Two of the three contracts (C-EVD evidence + C-TOL tool) are co-enforced by this single handoff condition.**

The HumanGate has the same pattern for C-APR approval:
```python
human_gate.register_handoffs([
    OnContextCondition(
        target=AgentTarget(agent=action),
        condition=StringContextCondition(variable_name="approval_granted"),
    ),
    OnContextCondition(target=TerminateTarget(), condition=None),
])
```

### Q4: Why register a `RegexGuardrail` if the handoff already gates progression?

Defense in depth. `zone_a/swarm.py:221-231`:

```python
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
```

The `OnContextCondition` reads `ContextVariables` after the tool function runs. The `RegexGuardrail` inspects raw LLM output before the tool function runs. If the LLM emits `tool_call_id: null` in its text, the guardrail catches it even if the tool function isn't invoked. Two independent C2 enforcement layers.

### Q5: Why use `register_for_llm` with tool functions?

So the LLM can update `ContextVariables` in a typed, traceable way. `zone_a/swarm_tools.py` defines six tools (one per agent role). Each takes a typed signature and a magic `context_variables: ContextVariables` parameter that AG2's `GroupToolExecutor` injects automatically. Each returns a `ReplyResult` with `(message, context_variables)`. The pattern:

```python
def record_verification(
    verified_sources_count: int,
    tool_call_id: str | None,
    narrative: str,
    context_variables: ContextVariables,
) -> ReplyResult:
    context_variables.set("verified_sources_count", verified_sources_count)
    context_variables.set("verifier_tool_call_id", tool_call_id or "")
    context_variables.set("sources_verified", verified_sources_count > 0 and bool(tool_call_id))
    return ReplyResult(message=..., context_variables=context_variables)
```

The LLM is forced to commit to typed values. No free-form prose can sneak past the contract gate.

### Q6: How is `ContextVariables` initialised?

`zone_a/swarm.py:102-120` — explicit `_initial_context()` returns a `ContextVariables(data={...})` with all 14 expected keys set to their default values. This guarantees every downstream `OnContextCondition` reads a defined value, never `None`. Important because `StringContextCondition` evaluates as truthy/falsy — undefined would behave non-deterministically across AG2 versions.

### Q7: Why `human_input_mode="ALWAYS"`?

That's how AG2 wires real human-in-the-loop. The `UserProxyAgent` blocks on stdin instead of auto-replying. We use it in two places:
- `zone_b/agents/human_gate.py:32-38` — Zone B's interactive HumanGate (operator approves the repair)
- `zone_a/agents/human_gate.py:27-33` — Zone A's interactive HumanGate (legacy sequential mode)
- `zone_a/swarm.py:170` — toggleable: `human_input_mode="ALWAYS" if interactive else "NEVER"`

The repair patch P-004 in the dashboard literally proposes adding `UserProxyAgent(human_input_mode="ALWAYS")` to fix the C-APR violation — **we use the same primitive the report recommends. The dogfood is real.**

### Q8: Why `temperature=0.1`?

`zone_a/config.py:16`. We're parsing every LLM response as structured JSON and extracting typed fields. Creative variation works against us — we want the same prompt to produce the same JSON shape across runs. 0.1 is low enough for stability, non-zero so the model doesn't hard-loop on degenerate completions.

### Q9: Why `max_consecutive_auto_reply=1`?

Every reasoning step is one turn. We don't want the agent to "think out loud" across multiple replies — that explodes token cost and produces non-deterministic chains. With `max_consecutive_auto_reply=1`, the proxy sends one message, the agent replies once, conversation ends, we parse the reply. Predictable.

### Q10: Where exactly does AG2's `Handoff` primitive show up in the proposed repair?

Two places:
- **Repair patch P-003** generated by `zone_b/agents/repair.py:15-21` PRIMITIVE_MAP for `routing` violations
- **Live in code** at `zone_a/swarm.py:201-219` via `register_handoffs([OnContextCondition(...)])`

The dashboard's P-003 patch shows this code:
```python
Handoffs(
    from_agent=VerifierAgent,
    to_agent=ReporterAgent,
    condition=OnContextCondition(...),
    forbidden_path=["CriticAgent", "ReporterAgent"],
)
```

That's the exact primitive Zone A's swarm already uses internally. Concord's repairs target the AG2 framework primitive layer because that's what the operator can paste straight into their workflow.

---

# Section 2 — TAVILY (where, how, what if it fails)

### Q11: Where is Tavily used?

Two places, both in Zone A:
- `zone_a/agents/researcher.py:46-58` — sequential pipeline. `TavilyClient(api_key=os.environ["TAVILY_API_KEY"]).search(query=research_question, max_results=3, search_depth="basic")`. Returns up to 3 sources. Always emits a `ToolEvent(tool_name="tavily_search", evidence_id="ev_001", status="success")` in the context delta.
- `zone_a/swarm.py:236-261` — swarm pipeline. `_build_initial_message()` pre-fetches Tavily results and embeds them in the swarm's first message so the Researcher has search context before its tool call.

### Q12: What if `TAVILY_API_KEY` is missing?

- Sequential mode (`researcher.py:48-51`): raises `EnvironmentError("TAVILY_API_KEY is not set. Add it to your .env file.")`. Hard fail — the run can't proceed without real search results.
- Swarm mode (`swarm.py:239-243`): graceful degradation — initial message says `"(no search results available — proceed with what you know)"`. The agent still runs, just without grounding.
- `--fixture` mode: never hits Tavily. Reads `zone_b/fixtures/sample_trace.json` directly. **This is the safe demo path.**

### Q13: What if Tavily returns zero results?

Researcher still runs — the LLM gets `[]` as the search input and produces a "no sources found" summary. Downstream, `verified_sources_count` would naturally be 0 and **the evidence contract C-EVD would fail with a real signal** (not a synthetic violation). We could choose to short-circuit before Reporter, but it's more honest to let the contract catch it.

### Q14: Why `max_results=3`?

Two reasons. (1) Token economy — three sources fits comfortably in the LLM's context with room for the system prompt and structured output. (2) The CriticAgent is told to flag weak sources — three is enough to demonstrate selection without overwhelming the demo.

### Q15: Why `search_depth="basic"` vs `"advanced"`?

Basic is faster (1-2s vs 5-10s) and cheaper. For a demo that needs to play live in 4 minutes, the tradeoff is correct. Advanced makes sense for production research but adds latency we don't need for showing the pipeline.

### Q16: Does Concord (Zone B) use Tavily?

No. Zone B is purely diagnostic — it reads traces, not the web. The only external service Zone B touches is Daytona (for running regression tests) and OpenRouter (for LLM calls). Tavily is exclusively a Zone A concern because Zone A is the workflow under test.

---

# Section 3 — DAYTONA (where, how, what if it fails)

### Q17: Where is Daytona used?

`zone_b/agents/regression_test.py` — `_run_in_daytona()` delegates to `zone_b.sandbox.run_python_in_daytona()`. Also `zone_b/sandbox_run.py` — a standalone runner that demonstrates the full Zone B pipeline executing inside a Daytona sandbox against a mock Tavily-enriched trace.

### Q18: What's the exact Daytona executor sequence?

```python
from autogen.coding import DaytonaCodeExecutor
from autogen.coding.base import CodeBlock

executor = DaytonaCodeExecutor(api_key=api_key, api_url=api_url, timeout=60)
result = executor.execute_code_blocks([CodeBlock(code=test_code, language="python")])
stdout = result.output
sandbox_id = result.sandbox_id
status = _parse_status(stdout)
```

Five things to note:
1. **Warm pool with reset** — `DaytonaExecutorPool` keeps N executors ready and calls `restart()` after each execution before reuse, so repeat runs avoid cold start without leaking sandbox state.
2. **`execute_code_blocks([...])`** — executes arbitrary Python inside Daytona. The test_code comes from the LLM or deterministic fallback.
3. **Pool cleanup** — `DaytonaExecutorPool.close()` calls `delete()` on every warm executor.
4. **Structured result** — the runner records `stdout`, `sandbox_id`, `duration_ms`, and cost fields.
5. **No `raise` on Daytona failure** — we return `("Daytona error: ...", "no-sandbox", "error")`. The pipeline continues; Reporter shows `regression_test_status="error"` honestly.

### Q19: What if `DAYTONA_API_KEY` or `DAYTONA_API_URL` is missing?

`zone_b/sandbox/runner.py`:
```python
if not _credentials_present():
    return execution_error("Daytona credentials missing")
```
Pipeline continues with `test_status="error"`. Reporter dutifully reports the error. No fake PASS — we don't lie about the regression result just because credentials are missing.

### Q20: What if the sandbox creation succeeds but the test crashes inside it?

`code_run()` returns whatever the script wrote to stdout. If the script crashed, stdout might be partial output or a traceback. `_parse_status()` (`regression_test.py:82-88`) is strict — it requires `PASS` and not `FAIL`. Crashes register as `"error"`. The `finally` block still deletes the sandbox.

### Q21: Why isn't the LLM-generated test code reviewed before execution?

Because Daytona is the review. The whole point of sandboxing is that we can run untrusted code without auditing it line by line. The sandbox image is `python:3.11-slim` — standard library only, no network, no host filesystem access. Worst-case the test crashes and we get an error status.

### Q22: How long does a Daytona run take?

Cold-start is still a few seconds, but the warm `DaytonaExecutorPool` keeps executors ready for repeat regression runs. Warm execution is expected to stay under roughly 2s for these generated tests.

### Q23: What if Daytona throttles us during the demo?

The pipeline still completes — we get an error status on the regression step but the report is still assembled. The dashboard would render `regression_test_status="error"` instead of `"pass"`. Not fatal. Worst case for the live demo: skip Mode A live runs and use the `--fixture` mode, which uses pre-recorded Daytona output baked into the fixture.

### Q24: Does Daytona run during the dashboard demo?

No — the live dashboard renders the pre-baked RUN-041 fixture which has Daytona stdout already captured. The Regression screen shows real Daytona output from a real prior run. Live Daytona execution happens when you run `python run_all.py` (full live mode) or `python zone_b/sandbox_run.py`.

---

# Section 4 — LLM (OpenRouter / Gemini)

### Q25: Where is the LLM configured?

Two files, identical pattern:
- `zone_a/config.py:7-17`
- `zone_b/config.py` (same shape)

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

### Q26: Why OpenRouter?

One API key, dozens of models. If Gemini is rate-limited or deprecated mid-demo, swap the model string and it works. Standardized on the OpenAI API shape (`api_type="openai"`) so AG2's `ConversableAgent` works without per-provider adapters.

### Q27: Why Gemini 2.5 Flash specifically?

Three reasons:
1. **Cheap** — sub-cent per request at our token volumes.
2. **Fast** — sub-second response times keep the demo snappy.
3. **JSON-friendly** — handles structured-output prompts well, which matters because every Zone B agent expects JSON back.

We're not generating long-form prose. We're parsing typed fields. Flash is the right tier.

### Q28: How many LLM calls per run?

Sequential mode, full live: **roughly 11 calls**.
- Zone A: Researcher (1) + Critic (1) + Verifier (1) + Reporter (1) + HumanGate (1) = 5
- Zone B: ContractChecker (3 — one per violation, for narrative text) + Attribution (1) + Repair (1) + RegressionTest (1, generates test code) + Reporter (1, narrative) = 7

About 11-12 LLM calls per full pipeline run. Bounded by `max_consecutive_auto_reply=1` per agent.

### Q29: What's the cost per run?

Gemini 2.5 Flash is ~$0.075 per million input tokens, ~$0.30 per million output tokens. Our total tokens per run hover around 30-50k. Per run: well under 1 cent. Hackathon-friendly.

### Q30: What if OpenRouter is down?

Sequential mode fails on the first LLM call. We'd swap to fixture mode for the demo. Long-term: AG2 supports failover config_lists — could add Anthropic / OpenAI as fallback config entries.

### Q31: Could you swap the model live?

Yes. Edit `model` arg in `get_llm_config()` or pass a different one at agent construction. AG2's `ConversableAgent` re-reads `llm_config` at construction; restart the pipeline and you're on a new model.

---

# Section 5 — DATA FLOW

### Q32: What's the exact data shape passed between Zone A and Zone B?

Zone A's `trace_emitter.py` writes a JSON file at `zone_b/fixtures/sample_trace.json`. Shape (from `shared/models.py:21-34`):

```python
RunTrace = {
    "run_id": str,
    "workflow_name": str,
    "events": [
        TraceEvent({
            "step": int,
            "agent": str,
            "type": str,            # agent_turn | handoff | tool_call | context_update
            "content": str,
            "tool_call_id": str | None,
            "context_delta": dict,  # may contain "tool_events": [ToolEvent, ...]
            "handoff_to": str | None,
            "timestamp": float,
        }),
        ...
    ],
    "final_output": Any,
}
```

That's the contract between zones. Anything matching this shape can be audited by Zone B.

### Q33: How does Zone B build its `ContextSnapshot`?

`zone_b/agents/trace_collector.py:43-69`. Walks every `TraceEvent` left-to-right, folds each `context_delta`:
- `tool_events` is **appended** (list extension) — preserves history
- Everything else is **last-write-wins** — final state wins

Then constructs a `ContextSnapshot` dataclass with seven fields. This is the snapshot the contract checker reads.

### Q34: Why fold deltas instead of treating events as immutable updates?

Because contracts care about *final* state, not intermediate state. "Did Reporter run with `verified_sources_count > 0`?" needs the count at Reporter's step, not at every step before it. Folding gives us the resolved value at any point.

### Q35: How does Zone B's report flow to the frontend?

Two paths:
- **Today (deployed):** doesn't. Frontend renders inline `window.CONCORD_DATA` fixture in `public/index.html`. Static deploy, no backend round-trip.
- **Wired but undeployed:** `api/index.py` exposes `GET /api/runs/{run_id}` returning the report. `api/adapter.py:report_to_concord_data()` converts the backend dict shape to the frontend's `CONCORD_DATA` shape. To go live, change one line in `index.html` to `<script src="/api/runs/RUN-041.js"></script>` (the `.js` endpoint returns `window.CONCORD_DATA = {...}` JSONP-style).

### Q36: Why is the dashboard fixture-only on Vercel?

Two reasons:
1. **Stage reliability** — no API round-trip means no flaky network on stage Wi-Fi.
2. **No serverless cold start** — the AG2 + autogen stack is too heavy for Vercel's Python serverless function size limits. Real backend integration needs a long-running host (Render, Railway, Fly.io). Out of scope for the hackathon timebox.

### Q37: How is `RunTrace` validated when it comes in?

`trace_collector.py:21-40` parses raw dict → `TraceEvent` dataclasses. Field access is by `e["step"]` (KeyError on missing required fields) and `e.get("tool_call_id")` (None on missing optional). Not Pydantic — but the dataclass parsing fails fast on a malformed trace, which is what we want at a system boundary.

---

# Section 6 — DETERMINISM & FAILURE HANDLING

### Q38: How do you guarantee determinism in contract checks?

Three layers:
1. **Lambda-based contracts** (`contract_checker.py:9-88`) — pure code, no LLM in the verdict.
2. **Deterministic primitive map** (`repair.py:15-21`) — `evidence → Guardrail`, `tool → OnContextCondition`, etc. Same violation type, same primitive, every time.
3. **Templated fallbacks** — when the LLM fails, every agent has a deterministic fallback path. Confidence drops from 0.85 to 0.5, but the report is still produced.

Same trace in → same violations and same primitive recommendations out. The narrative paragraph varies (it's LLM-generated), but the structured findings are reproducible.

### Q39: What happens if the LLM returns invalid JSON?

`zone_b/utils.py:parse_json_body()` raises. Each agent's caller catches and falls back:
- `attribution.py:96-114` — uses the first violation's `failed_agent`, deterministic step lookup
- `repair.py:97-102` — stub patch comment, confidence = 0.5
- `regression_test.py:164-178` — calls `_fallback_test()` which returns hard-coded test code that asserts the five enforced contracts
- `reporter.py:68-74` — uses templated narrative

We never crash on a bad LLM turn.

### Q40: How do you make sure a bad fixture doesn't break the pipeline?

`trace_collector.py` is strict on required fields (`step`, `agent`, `type`, `content`) — KeyError if missing. Optional fields (`tool_call_id`, `handoff_to`) default to None. So a malformed fixture fails fast at parse time instead of producing silently wrong contract verdicts.

### Q41: How do you handle Daytona being slow/down?

Already covered in Q19/Q23. Pipeline doesn't crash — `test_status="error"` propagates to the report. Reporter still assembles; Approval still runs. The operator sees the diagnostic with `regression_test_status="error"` instead of `"pass"`.

### Q42: What's the worst-case failure mode?

Worst case: every external dependency fails (Tavily, OpenRouter, Daytona). Then:
- Zone A can't run (TavilyClient init fails with `EnvironmentError`) — fall back to `--fixture` mode.
- Zone B's contract checker still runs (it's pure code). Violations are detected.
- Attribution falls back to deterministic mode.
- Repair falls back to templated patches.
- Regression test fails with `"error"`.
- Reporter still assembles using templated narrative.
- HumanGate auto-approves in demo mode.

You still get a Contract Violation Report. It's degraded (no LLM-generated narrative, no real regression PASS), but it's complete and honest.

---

# Section 7 — ARCHITECTURE / DESIGN DEFENSE

### Q43: Why two zones instead of one merged system?

Separation of concerns. Zone A is the *target* — any AG2 workflow under audit. Zone B is the *auditor* — workflow-agnostic. This separation means Zone B can audit ANY trace matching `shared/models.py`, not just the Literature Review demo. Replace Zone A with a customer-support workflow, a code-review workflow, a research synthesis workflow — Zone B doesn't change.

### Q44: Why a sequential pipeline in Zone B instead of an AG2 GroupChat?

Diagnostic data flow is a directed acyclic graph — each step's output is the next step's input. A GroupChat would add LLM-driven routing on top of an already-deterministic flow. We didn't want the LLM to sometimes skip Attribution because it "thought" the violation was clear enough. Determinism wins for diagnostics.

That said, **we built the GroupChat version anyway** in `zone_b/group_chat.py` using `RoundRobinPattern` + `ContextVariables` — same stage logic, GroupChat orchestration. Available, just not the default.

### Q45: Why `OnContextCondition` over plain `if`/`else` in Python?

Because `OnContextCondition` is the AG2 primitive operators already know. When Concord recommends "add `OnContextCondition` to gate this handoff", that's a one-line config change in the operator's existing workflow — no Python control flow refactor. Repair velocity matters more than implementation elegance.

### Q46: Why is the dashboard backend-disconnected for the demo?

Stage reliability. Wi-Fi can flake; serverless cold-starts can stall; LLM calls can rate-limit. Fixture mode means none of those can break the demo. The backend pipeline is what we're showing off — `python run_all.py --fixture` runs end-to-end in <30s with no network.

The wiring exists (`api/adapter.py`, `api/index.py`). It works locally. We chose not to deploy it because hackathon demos shouldn't depend on infrastructure outside the team's control.

### Q47: Could this work without AG2?

You could build the trace-checking + repair-mapping logic in any framework. But the *value* is the AG2-specific repair patches — Guardrail, OnContextCondition, HumanGate. Those are AG2 framework primitives. If you generalised to "any multi-agent framework", you'd lose the dogfood story (Concord uses AG2 to repair AG2) and the operator would have to translate the patch. AG2-native is the moat.

### Q48: Why is the proposed HumanGate already wired in the swarm?

`zone_a/swarm.py:166-172` registers HumanGateAgent as a real `ConversableAgent` with `human_input_mode="ALWAYS" if interactive else "NEVER"`. In `interactive=True` mode the swarm version actually waits for human approval before ActionAgent runs. **That means the swarm version's contracts are enforced at runtime, not just observed after the fact** — the `OnContextCondition` on `approval_granted` literally terminates the swarm if the human rejects.

The sequential mode (used for fixture generation) intentionally lets the violation happen so Zone B has something to detect. The swarm mode (used for "this is what fixed code looks like") prevents it.

### Q49: How would I add a new contract to this system?

Three steps:
1. Add a rule to `WORKFLOW_CONTRACT["rules"]` in `zone_a/workflow_contract.py` — declarative, IDs C1-C5.
2. Add a check lambda to `CONTRACTS = [...]` in `zone_b/agents/contract_checker.py` — `{"type": "...", "severity": "...", "rule": "...", "failed_agent": "...", "check": lambda trace, snap: ...}`.
3. Add the `(violation_type → AG2 primitive)` mapping to `PRIMITIVE_MAP` in `zone_b/agents/repair.py:15-21`.

That's it. No agent code changes. The pipeline picks up new contracts automatically because `contract_checker.py` iterates over the list.

### Q50: How would I support a new workflow (not Literature Review)?

Two steps:
1. Build your AG2 workflow as `ConversableAgent`s. Have it emit traces in the `RunTrace` shape (use `trace_emitter.py` as reference — it's a thin wrapper).
2. Update `WORKFLOW_CONTRACT` in `zone_a/workflow_contract.py` with your domain's rules. Or define a new contract file and point `contract_checker.py` at it.

Zone B is workflow-agnostic. The 7 diagnostic agents care about violations, not what the workflow does.

---

# Section 8 — FRONTEND SPECIFICS

### Q51: Why React via Babel-standalone instead of a build step?

Zero-build deployability. Drop the `index.html` on any static host (S3, Vercel, GitHub Pages) and it works. No `npm install`, no bundler config, no Vercel build minutes. Tradeoff is a "in-browser Babel transformer" warning in console — acceptable for a demo dashboard, not for production.

### Q52: Why is `window.CONCORD_DATA` inline in the HTML?

Three reasons:
1. **Single-file deployability** — `index.html` is self-contained, works offline.
2. **Zero round-trip** — first paint shows real data immediately.
3. **The original split files (`data.js`, `app.jsx`) failed with 401s in the AG2 chat preview environment** (per `HANDOFF.md`). Inlining was the workaround. Real HTTP serves the splits fine, but inlined version stayed because it was already working.

### Q53: How does the dashboard navigate between screens without a router?

`<App>` keeps `screen` state in `useState`. Tabs and node clicks set it via `setScreen("trace")` etc. Single-page app, no URL changes. Means refreshing always lands on Overview — acceptable for a 4-minute demo, would change for production.

### Q54: How does clicking a violation jump to its repair patch?

`Violations` component receives `setSelectedPatch` from `<App>`. On row click: `setSelectedPatch(matchedPatchId); setScreen("repair")`. The Repair component reads `selectedPatch` and filters the patch list. State flows top-down through props.

### Q55: How does the pipeline graph animate?

`<PipelineGraph>` uses `useState` for `currentStep` and `playing`. On REPLAY: `setCurrentStep(0)` then a `setInterval` that increments every ~520ms. Each agent's color is derived from `agentStateAt(agentId, currentStep)` which checks if any of that agent's trace steps are flagged FAIL up to the current step. Pure derived state — no animation library.

### Q56: Why no real-time updates from the backend?

Because there is no backend running in the deployed version. If we wired the live API, we'd add an SSE or polling layer; the React state model already supports it (just replace the inline data load with a fetch + setInterval poll).

---

# Section 9 — OPERATIONAL / META

### Q57: How do you run the test suite?

`pytest` at the repo root. The suite currently collects 328 tests across the API, Zone A, Zone B, integration, routing, schema, and per-violation regression coverage (see `README.md` Project Structure). Coverage includes:
- API persistence, workflow, and run submission behavior (`test_api_*.py`)
- Dataclass field integrity (`test_models.py`)
- Trace parsing and folding (`test_trace_collector.py`)
- Contract lambdas (`test_contract_checker.py`)
- Attribution fallback paths (`test_attribution.py`)
- Repair primitive map (`test_repair.py`)
- Regression test fallback (`test_regression_test.py`)
- Reporter assembly (`test_reporter.py`)
- Per-violation regression status (`test_per_violation_repairs.py`)
- HumanGate output shape (`test_human_gate.py`)
- Zone A integration (`test_zone_a.py`)
- Zone A→B end-to-end (`test_integration.py`)
- Edge cases and boundary conditions (`test_rigorous.py`)

### Q58: What's tested with real LLM calls?

None of the unit tests hit a live LLM. Tests use the deterministic fallback paths with mocked LLM clients. Integration tests are marked `@pytest.mark.integration` and require `OPENROUTER_API_KEY` to run — they're opt-in, not part of the default suite.

### Q59: How long does a full live pipeline run take?

Sequential mode with all integrations live: ~15-30s end-to-end.
- Zone A: ~8-12s (Tavily search 2-3s, 5 LLM calls 1-2s each)
- Zone B: ~10-15s (7 stages, of which Daytona is ~6-8s)
- HumanGate (auto-approve): instant

Fixture mode: ~10-15s (skips Zone A entirely).

### Q60: How big is the codebase?

~3000 lines of Python (counted earlier: `wc -l` on zone_a/, zone_b/, shared/). Plus ~2200 lines of inline HTML/JSX in `public/index.html`. Plus ~600 lines of CSS. Tight enough for one team to hold in their heads.

### Q61: What's the "dogfood" story exactly?

Concord's repair patches recommend AG2 primitives (`Guardrail`, `OnContextCondition`, `HumanGate`/`UserProxyAgent`). **Zone A's swarm mode (`zone_a/swarm.py`) literally uses those same primitives to enforce contracts at runtime.** So when Concord says "add OnContextCondition to gate this handoff" — that's not theoretical. The swarm version of Zone A already does it.

We use AG2 to repair AG2. That's the dogfood.

---

# Section 10 — FUNCTIONAL EDGE CASES

### Q62: What if the same agent has multiple violations?

`run_repair` emits one `patches[]` entry per violation, preserving input order. The legacy scalar fields still mirror the highest-severity patch, with ties broken by list order, so older callers keep working while newer callers consume the plural repair output.

### Q63: What if two contracts disagree?

Can't happen by construction — each contract checks an independent invariant. `evidence` checks `verified_sources_count`; `tool` checks `tool_call_id` presence; `routing` checks trace order; `approval` checks `approval_status`. Orthogonal axes. They can ALL fail simultaneously (and in our demo, four of them do), but they can't contradict.

### Q64: What if a trace has no violations?

ContractChecker returns `{violations: [], violation_count: 0}`. Attribution returns `{failed_agent: "", failed_step: -1, likely_root_cause: "no violations detected", attributions: []}` (`attribution.py:78-84`). Repair returns a no-op patch (`repair.py:74-81`). Reporter assembles a clean report. Approval is skipped or auto-approved. The pipeline runs to completion with all-green output — proves the diagnostic itself doesn't depend on violations existing.

### Q65: What if the trace has agents Concord doesn't know about?

Contract lambdas reference specific agent names (`VerifierAgent`, `ActionAgent`, etc). If your trace has different agent names, the checks return False (no matching agent) and you'd get either no violations or false negatives. That's by design — contracts are workflow-specific. To audit a different workflow, define new contracts referencing the new agent names.

### Q66: What if regression test stdout contains `PASS` AND `FAIL` (e.g., a failed assertion logged "expected PASS, got FAIL")?

`_parse_status:84` — `"PASS" in out and "FAIL" not in out` → returns `pass` only if PASS is present and FAIL is absent. If both substrings appear, status = `fail`. Conservative — false positives on PASS would be worse than false negatives.

### Q67: How does fallback test code know what to assert?

`_fallback_test:60-86` hard-codes assertions for the five enforced contracts (`verified_sources_count > 0`, `approval_status == "approved"`, `verifier_tool_call_id`, ordered Reporter/Action handoffs, and required final output keys). The fallback assumes the worst case and asserts they're all fixed. If the actual violations are a subset, the fallback over-tests but doesn't under-test.

### Q68: Why is the regression test self-contained Python?

Because it runs in a Daytona sandbox with `python:3.11-slim` and standard library only. No `pytest` install, no AG2 import, no external packages. Just pure Python that runs `assert` statements and prints `PASS` or `FAIL`. Keeps the sandbox light and deterministic.

### Q69: How does the system handle long-running workflows?

Today: sequential, blocking. Each agent waits for the previous one. Doesn't matter at our scale (12 events, ~30s total) but wouldn't scale to a 100-step workflow. Future: stream events into Zone B as they're emitted; ContractChecker becomes incremental; Reporter assembles partial reports.

### Q70: Could you watch a live workflow instead of post-hoc?

Yes. Replace the `_run_in_daytona` with a streaming endpoint and add a websocket from Zone B to the dashboard. The architecture supports it — we just chose post-hoc for the demo because it's simpler and more reproducible.
