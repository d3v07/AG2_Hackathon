# Meta-Prompt for ChatGPT — Concord (Full Version) Next Phase

Copy everything in the fenced block below into ChatGPT. It's a "prompt to get a prompt + docs" — ChatGPT returns (1) a detailed Claude prompt for executing the next phase and (2) the design docs Concord (main) will need.

---

````
You are a senior staff engineer + product architect helping plan the v1.0 of a multi-agent observability product called CONCORD. You will return TWO artifacts:

ARTIFACT A — A detailed prompt I can paste into Claude Code (Anthropic Opus) to execute the next phase of work. Claude will be working on the existing repo and needs concrete, file-pathed, copy-pasteable direction.

ARTIFACT B — Three design documents for Concord (the full v1.0 product, replacing what we currently call "Concord Lite"): a PRD, an architecture spec, and an AG2-feature-leverage plan.

------------------------------------------------------------
CONTEXT — WHAT EXISTS TODAY (Concord Lite, just won an AG2 hackathon)
------------------------------------------------------------

Repo: https://github.com/d3v07/AG2_Hackathon
Live demo (frontend only): https://concord-lite.vercel.app/
Stack: Python 3.12, AG2 (autogen), Tavily, Daytona, Gemini 2.5 Flash via OpenRouter, FastAPI for local API, React via Babel-standalone for static dashboard.

The product is a contract-to-repair layer for multi-agent workflows. It watches an AG2 workflow run, detects contract violations in the trace, attributes blame, generates an AG2-native repair patch, validates the patch in a Daytona sandbox, and produces a Contract Violation Report.

ARCHITECTURE (two zones):
- Zone A = the target AG2 workflow being audited (currently a Literature Review Assistant: Researcher → Critic → Verifier → Reporter → ActionAgent — 5 agents, intentionally broken to demo violations).
- Zone B = the diagnostic pipeline (7 agents: TraceCollector → ContractChecker → Attribution → Repair → RegressionTest → Reporter → HumanGate).

DUAL ORCHESTRATION:
- Sequential pipeline (zone_a/run.py + zone_b/orchestrator.py) — deterministic, demo-safe.
- AG2 swarm (zone_a/swarm.py + zone_b/group_chat.py) — uses RoundRobinPattern + ContextVariables + OnContextCondition + RegexGuardrail + register_for_llm tool functions.

WHAT'S WORKING TODAY:
- Real Tavily integration (zone_a/agents/researcher.py:46-58 — TavilyClient.search).
- Real Daytona integration (zone_b/agents/regression_test.py:91-117 — daytona_sdk.Daytona().create() → sandbox.process.code_run() → finally daytona.delete()).
- Real Gemini 2.5 Flash via OpenRouter (zone_a/config.py:7-17, temperature=0.1).
- 3 of 5 contracts enforced as deterministic Python lambdas (zone_b/agents/contract_checker.py:9-33): evidence (verified_sources_count > 0), tool (Verifier must record tool_call_id), approval (ActionAgent requires approval_status==approved).
- Deterministic primitive map (zone_b/agents/repair.py:15-21): evidence→Guardrail, tool→OnContextCondition, routing→Handoff, approval→HumanGate, schema→Guardrail.
- LLM generates the patch_code snippet and the regression test code; deterministic fallbacks if LLM returns invalid JSON.
- 226 unit + integration tests across 11 files.
- AG2 swarm uses real OnContextCondition + StringContextCondition handoffs and a RegexGuardrail for defense-in-depth (zone_a/swarm.py:201-231).
- UserProxyAgent with human_input_mode="ALWAYS" wired in three places for real human approval.
- Dashboard is 7 screens: Overview (animated pipeline), Workflow DAG, Agent Trace, Violations, Repair Patch, Regression, Final Report. Currently fixture-driven (window.CONCORD_DATA inline in public/index.html).
- FastAPI local server (api/index.py) with adapter (api/adapter.py) that converts a real Zone B report dict into the dashboard's CONCORD_DATA shape — works locally, not deployed (Vercel can't host the AG2 stack at function size limits).

EXISTING DOCS in repo:
- docs/ARCHITECTURE.md — 11-section walkthrough.
- docs/DEMO_SCRIPT.md — 59 verbatim cue cards.
- docs/QA_DEEP.md — 70 deep Q&A with file:line refs.
- docs/PLAN_VS_REALITY.md — Northstar plan vs delivered scorecard.

HONEST GAPS in v0:
1. Routing (C-RTE) and Schema (C-SCH) contracts declared in zone_a/workflow_contract.py but not yet enforced as lambdas in contract_checker.py. C-RTE IS enforced at runtime in the swarm via OnContextCondition.
2. Backend produces ONE primary patch per run (_pick_primary). Dashboard shows 4 (templated).
3. Workflow DAG topology is fixture-only — doesn't yet derive from a parsed AG2 program.
4. Live dashboard is fixture-driven — API not deployed publicly.
5. No POST /api/runs to submit a new workflow — Zone A is CLI-only today.
6. No persistent storage — runs live in an in-memory dict (api/store.py).
7. No multi-tenancy, no auth, no per-user runs.
8. No live workflow streaming — diagnostic is post-hoc only.

------------------------------------------------------------
WHAT WE WANT NEXT (Concord v1.0 — the full product, NOT Lite)
------------------------------------------------------------

We just won a hackathon and have:
- $1000 of Daytona credit
- AG2 partnership / heavy AG2 usage agreed
- Gemini API access at scale

The v1.0 product needs to be a real SaaS-ready application that any AG2 developer can point at their own multi-agent workflow and get back contract violations + repairs. NOT a demo. NOT fixture-driven. Real.

DEEP AG2 LEVERAGE I want explored (you the architect should also suggest more):
- FalkorDB integration — graph database for agent memory + workflow topology storage. AG2 supports it via the autogen.agentchat.contrib.graph_rag patterns. Use it to (a) store every workflow's declared topology so we don't fixture-mock it, (b) build a persistent memory layer for repeat-violation detection across runs, (c) power graph-based queries on the violation history.
- Mem0 / memory layer — persistent agent memory across runs so Concord can say "we've seen this violation pattern 8 times in this workflow over the last week".
- AG2 Captain Agent — hierarchical orchestration where a top-level agent decides whether to invoke Zone B at all (e.g., skip diagnostic if trace is shorter than N events).
- ReasoningAgent — chain-of-thought style attribution for complex multi-violation cases.
- DocAgent — let operators upload their workflow's design doc (PDF / markdown) and have Concord cross-reference declared intent vs observed behavior.
- WebSurfer — for cases where the contract refers to external documentation that needs verifying.
- Nested chats — for the Repair → RegressionTest loop where Repair generates a patch, RegressionTest evaluates it, and the loop iterates until pass.
- AG2's logging/tracing module — replace our hand-rolled trace_emitter.py with AG2's native runtime instrumentation.
- AG2 Studio integration — let users design custom contracts via a visual builder.
- AG2 GraphQL — for the dashboard query layer.
- AG2 streaming responses — for live workflow audit (not post-hoc).
- Custom speaker selection — replace RoundRobinPattern with intelligent stage-skipping (e.g., skip Attribution if there's only one violation).
- Real Handoffs() class instead of OnContextCondition handoff registration — tighter pattern for the production version.
- AG2 + LangGraph adapter — interop with workflows built in LangGraph.
- AG2 Twilio / voice — for HumanGate via phone call ("Press 1 to approve the repair, 2 to reject").
- Per-LLM-provider routing — run cheap calls on Gemini Flash, expensive ones on Gemini Pro, with cost tracking.

REQUIRED v1.0 CAPABILITIES (you should add more):
1. POST /api/workflows — register a workflow (name, declared topology, contract list).
2. POST /api/runs — submit a new run trace OR a task spec that runs Zone A first.
3. GET /api/runs/{id} — full report + live status if in-progress.
4. Live dashboard with WebSocket push — runs update in real time, not on poll.
5. Persistent storage — FalkorDB for graph data + Postgres or SQLite for relational.
6. Multi-tenancy — each customer has isolated runs, contracts, workflows.
7. Auth — API key per tenant + dashboard SSO.
8. Per-violation patches with diff-grade quality (real before/after of the operator's actual code, not templates).
9. Schema and Routing contracts enforced as code (close the v0 gap).
10. Custom contract DSL — operators write their own contract lambdas via a YAML or Python config.
11. Repair → Test → Iterate loop — if regression test fails, regenerate patch up to N times.
12. Daytona pool management — spin sandboxes from a warm pool to cut cold-start latency.
13. Cost dashboard — per-run cost breakdown across LLM, Daytona, Tavily.
14. Slack / Discord / email notifications for HumanGate approvals.
15. SDK — pip-installable concord-sdk for instrumenting AG2 workflows in one line.
16. Public landing page + signup + onboarding flow.
17. Marketing site at concord.dev (or whatever we register).

NON-GOALS (for v1.0):
- Don't try to support every multi-agent framework. AG2-first. LangGraph adapter is a stretch.
- Don't build a no-code workflow builder. We're tooling, not a workflow IDE.
- Don't try to reach feature parity with LangSmith / Helicone. We're a contract layer, not generic observability.

DESIGN PRINCIPLES (carry over from v0):
- Determinism wins. Every contract verdict is reproducible. LLM only generates human-readable narrative, never the verdict.
- Defense in depth. RegexGuardrail + OnContextCondition pair was the right call.
- Honest fallbacks. Every LLM call has a deterministic fallback path.
- Sponsor integrations are real, not stubs.
- Ship vertical slices. One complete user-visible path before starting the next.

------------------------------------------------------------
WHAT YOU (CHATGPT) MUST RETURN
------------------------------------------------------------

ARTIFACT A — Claude Code execution prompt
The format is a single fenced markdown block that I will paste into Claude. The prompt should:
1. Open with a one-paragraph mission statement (Concord v1.0, what changes vs Lite).
2. Reference the existing repo paths Claude already knows (zone_a/, zone_b/, shared/, api/, public/, docs/).
3. Specify a sprint plan as numbered phases. Each phase = a vertical slice (one complete user-visible capability). For each phase, give:
   - Goal (one sentence).
   - Files to create / modify (with paths).
   - AG2 primitives to use (named).
   - Acceptance criteria (testable).
   - Risks + mitigations.
4. End with an explicit "STOP after Phase X for user confirmation" gate.
5. Bake in our priors: SOLID/DRY/KISS/YAGNI, no comments unless WHY is non-obvious, no AI mentions in commits, parallel tool calls where possible, never delegate understanding.
6. Be as long as it needs to be. Do not pad. Do not omit.

ARTIFACT B — Three Concord v1.0 design docs
Each as a separate fenced markdown block, formatted as if it were a file in docs/. Suggested files:
1. CONCORD_PRD.md — product requirements: target users, core jobs-to-be-done, the v1.0 feature set with priorities (P0/P1/P2), success metrics, what we are NOT building.
2. CONCORD_ARCHITECTURE.md — system architecture: components, data flow, persistence model (FalkorDB schema, Postgres schema), API contract, AG2 pattern usage table, deployment topology (frontend / API / worker / DB / sandbox pool), security model.
3. CONCORD_AG2_LEVERAGE.md — exhaustive table of every AG2 component / pattern / contrib module we should use, what for, with code stubs showing the integration shape. Cover at minimum: FalkorDB, Mem0, Captain Agent, ReasoningAgent, DocAgent, WebSurfer, Nested chats, Custom speaker selection, Handoffs class, AG2 streaming, AG2 logging/tracing, AG2 Studio, AG2 + LangGraph adapter, AG2 Twilio / voice (only if it makes product sense), per-provider LLM routing. Add anything else you think a senior AG2 engineer would reach for.

GROUND RULES FOR YOUR OUTPUT:
- No marketing fluff ("revolutionize", "blazingly fast", "supercharge").
- No emoji unless I explicitly use one in this prompt (I haven't).
- Cite specific AG2 module paths where you mention them (e.g., autogen.agentchat.contrib.captainagent).
- If you don't know whether an AG2 feature exists, say "verify via docs" rather than inventing.
- Be opinionated. If two patterns are viable, pick one and say why.
- Honor the v0 honest concessions — don't pretend we already solved them. The next phase is what closes them.
- File paths must be unix-style relative paths from repo root.
- All deliverables in markdown. No screenshots, no images.
- Total response length: as long as the work demands. Do not artificially truncate.

Begin now. Output ARTIFACT A first, then ARTIFACT B (each doc as its own block).
````

---

## How to use this

1. Copy the entire fenced block above (between the triple backticks).
2. Paste it into ChatGPT (GPT-5 if available; GPT-4 turbo otherwise — needs the long context).
3. ChatGPT returns ARTIFACT A (paste into Claude) + ARTIFACT B (commit to `docs/`).
4. Run Claude on ARTIFACT A. It should respect the phase gates — review each phase output before approving the next.

## Why this shape

- **"Prompt to get a prompt"** because ChatGPT is good at generating structured Claude prompts; Claude is good at executing them on a real codebase. Different strengths.
- **Two artifacts in one ChatGPT round-trip** saves you a second ceremony — you get docs AND execution in one shot.
- **Explicit ground rules** so ChatGPT doesn't pad or invent AG2 features that don't exist.
- **The "honest concessions" framing** keeps the next phase grounded — we close v0 gaps before adding shiny new stuff.
