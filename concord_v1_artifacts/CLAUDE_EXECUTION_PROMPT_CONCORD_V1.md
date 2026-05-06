# Claude Code Execution Prompt - Concord v1.0 Long-Term Product

Copy this entire prompt into Claude Code while working inside the existing repository.

---

## Mission

You are working on Concord v1.0, the long-term version of the hackathon project Concord Lite. Concord Lite proved a single AG2 demo path: a broken target workflow was diagnosed and turned into a contract violation report. Concord v1.0 must become a real AG2-first, SaaS-ready contract-to-repair platform for multi-agent workflows.

The product is not generic observability. It is not a prettier AG2 Failure Attribution UI. It is not a no-code workflow builder. Concord v1.0 lets AG2 developers register workflows, submit traces or live runs, enforce deterministic contracts, generate per-violation repair patches, validate patches through Daytona, store recurring violation patterns, and expose everything through an API-backed live dashboard.

Core product sentence:

> Concord reads a multi-agent workflow trace plus its workflow contract, detects contract violations, maps each violation to the broken primitive, generates a repair patch, validates it with a regression test, and stores the learning so the same failure does not return.

## Existing repository context

Repo paths to inspect and use:

```text
zone_a/      Target AG2 workflow under test
zone_b/      Concord diagnostic pipeline
shared/      Shared schemas and utilities
api/         FastAPI API and adapters
public/      Current static dashboard
docs/        Architecture, demo, Q&A, reality docs
tests/       Unit and integration tests
```

Current stack:

```text
Python 3.12
AG2 / autogen
Tavily
Daytona
Gemini 2.5 Flash through OpenRouter
FastAPI local API
Static dashboard in public/index.html
```

Current known working state:

- Zone A target workflow exists as a Literature Review Assistant.
- Zone B diagnostic pipeline exists.
- Tavily integration exists in Zone A researcher.
- Daytona integration exists in Zone B regression test generation.
- Gemini configuration exists through OpenRouter.
- Evidence, Tool, and Approval contracts are enforced deterministically.
- Routing and Schema contracts are declared but not fully enforced as deterministic checks.
- Backend currently produces one primary patch per run.
- Dashboard currently shows fixture-driven data.
- API exists locally but public demo is frontend-only.
- No persistent storage.
- No `POST /api/workflows`.
- No `POST /api/runs` for real user-submitted traces.
- No tenant/auth layer.
- No live workflow streaming.

## Product boundary

Concord Lite:

```text
One demo workflow -> one diagnostic report -> one hackathon artifact
```

Concord v1.0:

```text
Registered workflows -> submitted traces/runs -> deterministic contract checks -> per-violation repair patches -> regression tests -> stored run history -> live dashboard -> tenant-ready API
```

Long-term Concord Platform:

```text
Contract engine + trace adapters + repair engine + regression test engine + violation memory + agent trust/admission + framework adapters
```

Important distinction:

- AG2 Failure Attribution answers: who failed and when.
- Concord answers: what contract was violated, what primitive broke, what repair patch should be applied, and what regression test prevents recurrence.

## Engineering principles

Follow these rules:

- SOLID, DRY, KISS, YAGNI.
- Determinism wins. Contract verdicts must be reproducible.
- LLMs may explain, summarize, or draft repair text. LLMs must not own deterministic verdicts.
- Every LLM path needs a deterministic fallback.
- No fake production claims.
- If something is mocked or simulated, label it honestly in code and docs.
- No comments unless the WHY is non-obvious.
- No AI mentions in commits, comments, PR titles, or code comments.
- Use parallel tool calls where possible.
- Never delegate understanding. Read files before modifying them.
- Keep the current demo path working.
- End every phase with tests.
- AG2-first. Do not build broad framework support before the AG2 wedge is stable.
- Do not build a generic observability product.
- Do not build a no-code workflow builder.

## Phase plan

Work in phases. Each phase is a vertical slice. Stop after Phase 1 for user confirmation.

---

## Phase 0 - Repo audit and safety baseline

### Goal

Understand the current repo, confirm current behavior, and record the truth before changing anything.

### Files to inspect

```text
README.md
pyproject.toml
requirements.txt
zone_a/run.py
zone_a/swarm.py
zone_a/workflow_contract.py
zone_a/config.py
zone_a/agents/researcher.py
zone_b/orchestrator.py
zone_b/group_chat.py
zone_b/agents/contract_checker.py
zone_b/agents/repair.py
zone_b/agents/regression_test.py
api/index.py
api/adapter.py
api/store.py
public/index.html
docs/ARCHITECTURE.md
docs/PLAN_VS_REALITY.md
tests/
```

### Tasks

1. Run the full test suite.
2. Start the local API if instructions exist.
3. Confirm how Zone A generates traces.
4. Confirm how Zone B consumes traces.
5. Confirm how the dashboard fixture shape maps to the Zone B report.
6. Write `docs/NEXT_PHASE_AUDIT.md`.

### Acceptance criteria

- Tests run and result is recorded.
- No behavior changes.
- `docs/NEXT_PHASE_AUDIT.md` includes:
  - what is live
  - what is mocked
  - what tests pass or fail
  - exact v0 gaps remaining

### Risks and mitigations

- Risk: failing tests were already failing.
  - Mitigation: separate pre-existing failures from new failures.
- Risk: current behavior depends on fixture shape.
  - Mitigation: document adapter expectations before changing schemas.

---

## Phase 1 - Contract engine hardening and per-violation repair patches

### Goal

Close the core v0 correctness gaps by enforcing Routing and Schema contracts as deterministic checks, and return one repair patch per violation.

### Files to create

```text
shared/contracts.py
shared/trace.py
shared/violations.py
shared/repairs.py
zone_b/contracts/__init__.py
zone_b/contracts/types.py
zone_b/contracts/checks.py
zone_b/contracts/registry.py
```

### Files to modify

```text
zone_a/workflow_contract.py
zone_b/agents/contract_checker.py
zone_b/agents/repair.py
zone_b/agents/regression_test.py
zone_b/orchestrator.py
zone_b/group_chat.py
api/adapter.py
api/index.py
tests/
docs/PLAN_VS_REALITY.md
docs/NEXT_PHASE_AUDIT.md
```

### AG2 primitives to use

- Existing AG2 diagnostic GroupChat.
- Existing RoundRobin or deterministic sequence for stability.
- ContextVariables where already wired.
- OnContextCondition for routing-aware repair examples.
- RegexGuardrail for schema and citation guardrail repair examples.
- UserProxyAgent remains the human approval gate.
- Do not introduce CaptainAgent or ReasoningAgent yet.

### Required deterministic contract checks

Implement five contract checks behind one registry.

#### C-EVD Evidence contract

Rule:

```text
ReporterAgent cannot produce final output unless verified_sources_count > 0.
```

Repair primitive:

```text
Guardrail + optional ContextVariables requirement.
```

#### C-TOL Tool contract

Rule:

```text
Any claim that search, external verification, or execution happened must have a matching tool event.
```

Repair primitive:

```text
Tool event requirement + OnContextCondition before verdict.
```

#### C-APP Approval contract

Rule:

```text
ActionAgent cannot perform side effects unless approval_status == approved.
```

Repair primitive:

```text
UserProxyAgent / HumanGate.
```

#### C-RTE Routing contract

Rules:

```text
ReporterAgent must not run before VerifierAgent.
ActionAgent must not be reachable before HumanGate if side effects exist.
```

Repair primitive:

```text
Handoff / OnContextCondition.
```

#### C-SCH Schema contract

Rule:

```text
Final report must include required fields: summary, claims, citations, confidence, next_steps.
```

Repair primitive:

```text
Guardrail + schema enforcement.
```

### Required output shape

Every violation must return this structure:

```python
{
    "violation_id": "v_...",
    "contract_code": "C-EVD",
    "contract_type": "evidence",
    "severity": "high",
    "expected": "...",
    "observed": "...",
    "evidence": [
        {
            "event_id": "...",
            "step": 6,
            "agent": "ReporterAgent",
            "field": "verified_sources_count",
            "value": 0
        }
    ],
    "failed_agent": "ReporterAgent",
    "failed_step": 6,
    "affected_primitive": "Guardrail",
    "repair_patch": {
        "title": "...",
        "summary": "...",
        "patch_code": "...",
        "before": "...",
        "after": "..."
    },
    "regression_test": {
        "name": "...",
        "assertions": [],
        "code": "...",
        "status": "pending"
    }
}
```

### Implementation guidance

- Move verdict logic out of agent prompts into deterministic functions.
- Contract checker agent can explain verdicts, but it must not invent verdicts.
- Repair agent gets deterministic violation objects and maps them to patch types.
- Keep old dashboard shape working by adding compatibility fields.
- Remove single `_pick_primary` limitation only after adapter supports multiple repair patches.
- If LLM patch JSON is invalid, deterministic fallback must return a valid patch and test.

### Tests to add

```text
tests/test_contract_checks.py
tests/test_routing_contract.py
tests/test_schema_contract.py
tests/test_per_violation_repairs.py
tests/test_api_adapter_multi_patch.py
```

### Acceptance criteria

- Existing tests pass or pre-existing failures are documented.
- Routing contract is enforced as deterministic code.
- Schema contract is enforced as deterministic code.
- Every violation gets its own repair patch.
- Every violation gets its own regression test.
- Dashboard adapter can render multiple real patches.
- Current demo fixture path still works.

### Risks and mitigations

- Risk: schema drift between Zone A and Zone B.
  - Mitigation: shared types in `shared/`.
- Risk: refactor becomes too broad.
  - Mitigation: add registry and adapters first.
- Risk: LLM patch generation creates nondeterministic tests.
  - Mitigation: test deterministic fallbacks.

STOP after Phase 1 and report:

1. files changed
2. tests added
3. tests passing/failing
4. remaining risks
5. recommendation for Phase 2

Ask for user confirmation before continuing.

---

## Phase 2 - Persistent workflows and run registration

### Goal

Turn Concord from a CLI/demo flow into an API-backed product where users register workflows and submit traces.

### Files to create or modify

```text
api/models.py
api/db.py
api/store.py
api/index.py
api/schemas.py
api/routes/workflows.py
api/routes/runs.py
api/routes/reports.py
api/migrations/
shared/schemas.py
tests/test_api_workflows.py
tests/test_api_runs.py
```

### Storage

Use SQLite locally through SQLAlchemy or SQLModel, with a clean Postgres migration path.

### Endpoints

```text
POST /api/workflows
GET /api/workflows
GET /api/workflows/{workflow_id}
POST /api/runs
GET /api/runs/{run_id}
GET /api/runs/{run_id}/report
```

### Acceptance criteria

- Workflow persists across server restart.
- Contracts validate on create.
- Run submission stores trace and starts analysis.
- Report can be retrieved by run ID.

---

## Phase 3 - Native AG2 trace ingestion and Concord SDK

### Goal

Replace hand-rolled trace capture with AG2 native tracing where possible, while preserving current trace JSON compatibility.

### Files to create or modify

```text
sdk/concord_sdk/__init__.py
sdk/concord_sdk/client.py
sdk/concord_sdk/instrumentation.py
zone_a/trace_adapter.py
api/trace_ingest.py
tests/test_sdk_instrumentation.py
```

### AG2 primitives

Use AG2 OpenTelemetry instrumentation:

```text
autogen.opentelemetry.instrument_agent
autogen.opentelemetry.instrument_llm_wrapper
autogen.opentelemetry.instrument_pattern
autogen.opentelemetry.instrument_a2a_server later
```

### Acceptance criteria

- Developer can instrument an AG2 workflow with one line.
- Native AG2 trace spans convert into Concord RunTrace.
- Existing v0 trace JSON still works.

---

## Phase 4 - Live dashboard streaming

### Goal

Make the dashboard live instead of fixture-driven.

### Files to create or modify

```text
api/events.py
api/ws.py
api/routes/events.py
frontend/ or public/ migration files
tests/test_streaming_events.py
```

### AG2 primitives

- Prefer AG-UI if it fits the dashboard model.
- Otherwise implement Concord-specific SSE/WebSocket first and add AG-UI adapter later.

### Acceptance criteria

- Run status updates without page refresh.
- Trace, tool events, violations, repairs, tests, and report update progressively.
- Fixture mode remains available for demos.

---

## Phase 5 - Daytona repair and test loop

### Goal

Make regression tests real enough to matter.

### Files to create or modify

```text
zone_b/sandbox/daytona_pool.py
zone_b/sandbox/runner.py
zone_b/agents/regression_test.py
tests/test_daytona_runner.py
```

### AG2 primitive

```text
autogen.coding.DaytonaCodeExecutor
```

### Acceptance criteria

- Generated regression test can run in Daytona.
- Sandbox lifecycle is safe.
- Fallback local/simulated runner exists.
- Report includes stdout, stderr, pass/fail, and assertions.

---

## Phase 6 - FalkorDB workflow graph and violation memory

### Goal

Store workflow topology and violation history as graph data.

### Files to create or modify

```text
graph/falkor.py
graph/schema.py
graph/queries.py
zone_b/memory/violation_memory.py
tests/test_graph_schema.py
```

### AG2 primitives

Verify exact installed import paths before coding:

```text
autogen.agentchat.contrib.graph_rag.falkor_graph_query_engine.FalkorGraphQueryEngine
autogen.agentchat.contrib.graph_rag.falkor_graph_rag_capability.FalkorGraphRagCapability
```

### Acceptance criteria

- Workflow topology persists as graph nodes and edges.
- Recurring violation patterns can be queried.
- Dashboard can show recurrence count.

---

## Phase 7 - Contract DSL

### Goal

Let operators define workflow contracts in YAML first, Python later.

### Files to create or modify

```text
contracts/dsl.py
contracts/parser.py
contracts/examples/*.yaml
tests/test_contract_dsl.py
```

### Acceptance criteria

- YAML contract compiles into deterministic checks.
- Invalid DSL gives a helpful error.
- Existing Python contract path still works.

---

## Phase 8 - Tenant, auth, and cost dashboard

### Goal

Make Concord SaaS-ready enough for pilots.

### Files to create or modify

```text
api/auth.py
api/tenancy.py
api/costs.py
shared/tenancy.py
tests/test_auth.py
tests/test_tenancy.py
```

### Acceptance criteria

- API key per tenant.
- Tenant-isolated workflows and runs.
- Per-run cost includes LLM, Tavily, and Daytona.

---

## Phase 9 - Deployment and onboarding

### Goal

Ship a hosted path.

### Files to create or modify

```text
Dockerfile
docker-compose.yml
.github/workflows/ci.yml
docs/DEPLOYMENT.md
docs/ONBOARDING.md
landing/
```

### Acceptance criteria

- One-command local stack.
- CI runs tests.
- Hosted frontend can talk to hosted backend.
- First-time user can register workflow and submit trace.

---

## Final instruction

Start with Phase 0, then Phase 1. Stop after Phase 1 for user confirmation.
