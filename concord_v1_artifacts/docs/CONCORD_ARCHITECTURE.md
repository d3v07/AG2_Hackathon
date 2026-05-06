# Concord Architecture

## 1. Architecture summary

Concord v1.0 is an AG2-first contract-to-repair system.

It has five layers:

1. Client layer
2. API layer
3. Worker / diagnostic engine
4. Persistence layer
5. Sandbox / integration layer

The key product path:

```text
workflow registration
  -> run submission
  -> trace normalization
  -> deterministic contract checks
  -> diagnostic agent explanation
  -> repair patch generation
  -> regression test generation
  -> Daytona validation
  -> report persistence
  -> live dashboard update
```

## 2. Component overview

### 2.1 Frontend

Responsibilities:

- workflow list
- workflow detail
- run dashboard
- live trace view
- violation detail
- repair patch diff
- regression test result
- final report
- cost view
- approval actions

Recommended migration:

```text
frontend/
  src/
    app/
    components/
    pages/
    lib/api.ts
    lib/types.ts
```

Keep `public/` fixture mode until the new app is stable.

### 2.2 API server

Responsibilities:

- auth
- tenant isolation
- workflow registration
- run submission
- report retrieval
- live status streaming
- dashboard data API

Suggested stack:

- FastAPI
- SQLAlchemy or SQLModel
- Pydantic models
- WebSocket or SSE
- background worker queue

Suggested paths:

```text
api/
  index.py
  routes/
    workflows.py
    runs.py
    reports.py
    auth.py
    streaming.py
  schemas.py
  db.py
  models.py
  auth.py
  tenancy.py
  costs.py
```

### 2.3 Worker / diagnostic engine

Responsibilities:

- normalize traces
- run contract checks
- run diagnostic GroupChat if needed
- generate repairs
- generate regression tests
- call Daytona
- call Tavily
- persist outputs

Suggested paths:

```text
worker/
  main.py
  jobs.py
  queue.py

zone_b/
  orchestrator.py
  group_chat.py
  contracts/
    types.py
    registry.py
    checks.py
    dsl.py
  agents/
    trace_collector.py
    contract_checker.py
    attribution.py
    repair.py
    regression_test.py
    reporter.py
  sandbox/
    daytona_pool.py
    runner.py
  memory/
    violation_memory.py
```

### 2.4 SDK

Responsibilities:

- instrument AG2 workflow
- emit traces
- submit runs
- optionally register workflow
- local dev helper

Suggested paths:

```text
sdk/
  concord_sdk/
    __init__.py
    client.py
    instrumentation.py
    schemas.py
```

### 2.5 Persistence layer

Use two stores:

1. Relational DB for transactional product data.
2. FalkorDB graph for workflow topology and violation pattern memory.

P0 can start with SQLite for local dev and a Postgres-compatible schema.

P1 adds FalkorDB.

## 3. Data flow

### 3.1 Register workflow

```text
client
  -> POST /api/workflows
  -> validate workflow schema
  -> persist workflow
  -> persist contracts
  -> optionally persist topology in FalkorDB
  -> return workflow_id
```

### 3.2 Submit run trace

```text
client or SDK
  -> POST /api/runs
  -> create run row
  -> enqueue analysis job
  -> return run_id
```

### 3.3 Analyze run

```text
worker
  -> load workflow contract
  -> normalize trace
  -> run deterministic contract checks
  -> create violations
  -> run diagnostic agents for explanation and repair narrative
  -> generate per-violation repair patches
  -> generate tests
  -> run or simulate tests in Daytona
  -> persist report
  -> emit dashboard events
```

### 3.4 Dashboard live update

```text
frontend subscribes to /api/runs/{id}/events
  -> RUN_STARTED
  -> TRACE_NORMALIZED
  -> CONTRACT_CHECKED
  -> VIOLATION_FOUND
  -> REPAIR_GENERATED
  -> TEST_RUNNING
  -> TEST_PASSED or TEST_FAILED
  -> REPORT_READY
```

## 4. Core schemas

### Workflow

```json
{
  "workflow_id": "wf_123",
  "tenant_id": "tenant_abc",
  "name": "Literature Review Assistant",
  "framework": "ag2",
  "topology": {
    "agents": [
      {"name": "ResearcherAgent", "type": "ConversableAgent"},
      {"name": "CriticAgent", "type": "ConversableAgent"},
      {"name": "VerifierAgent", "type": "ConversableAgent"},
      {"name": "ReporterAgent", "type": "ConversableAgent"},
      {"name": "ActionAgent", "type": "ConversableAgent"}
    ],
    "edges": [
      {"from": "ResearcherAgent", "to": "CriticAgent"},
      {"from": "CriticAgent", "to": "VerifierAgent"},
      {"from": "VerifierAgent", "to": "ReporterAgent"},
      {"from": "ReporterAgent", "to": "ActionAgent"}
    ]
  },
  "contracts": []
}
```

### RunTrace

```json
{
  "run_id": "run_123",
  "workflow_id": "wf_123",
  "events": [
    {
      "event_id": "evt_1",
      "step": 1,
      "timestamp": "2026-05-03T12:00:00Z",
      "agent": "ResearcherAgent",
      "type": "agent_turn",
      "content": "...",
      "tool_call_id": null,
      "context_delta": {},
      "handoff_to": "CriticAgent"
    }
  ],
  "final_output": {}
}
```

### Contract

```json
{
  "contract_id": "contract_123",
  "code": "C-EVD",
  "type": "evidence",
  "name": "Reporter requires verified sources",
  "severity": "high",
  "rule": {
    "agent": "ReporterAgent",
    "requires": {
      "verified_sources_count": {"gt": 0}
    }
  }
}
```

### Violation

```json
{
  "violation_id": "v_123",
  "run_id": "run_123",
  "contract_id": "contract_123",
  "contract_code": "C-EVD",
  "severity": "high",
  "expected": "ReporterAgent requires verified_sources_count > 0",
  "observed": "verified_sources_count = 0",
  "evidence": [
    {
      "event_id": "evt_6",
      "step": 6,
      "agent": "ReporterAgent",
      "field": "verified_sources_count",
      "value": 0
    }
  ],
  "failed_agent": "ReporterAgent",
  "failed_step": 6,
  "affected_primitive": "Guardrail"
}
```

### RepairPatch

```json
{
  "repair_id": "repair_123",
  "violation_id": "v_123",
  "affected_primitive": "Guardrail",
  "title": "Block Reporter without verified sources",
  "summary": "Add a guardrail requiring verified_sources_count > 0 before ReporterAgent can produce the final report.",
  "before": "ReporterAgent can run with verified_sources_count = 0",
  "after": "ReporterAgent is blocked or routed back to ResearcherAgent",
  "patch_code": "...",
  "requires_approval": true
}
```

### RegressionTest

```json
{
  "test_id": "test_123",
  "violation_id": "v_123",
  "name": "test_reporter_requires_verified_sources",
  "assertions": [
    "ReporterAgent must not produce final output when verified_sources_count == 0"
  ],
  "code": "...",
  "status": "passed",
  "runner": "daytona",
  "stdout": "...",
  "stderr": ""
}
```

## 5. Relational schema

Use SQLite locally, Postgres in production.

Tables:

```text
tenants
api_keys
workflows
contracts
runs
trace_events
violations
repair_patches
regression_tests
tool_events
cost_records
approval_events
```

Every tenant-owned row must contain `tenant_id`.

### Critical indexes

```text
workflows(tenant_id)
runs(tenant_id, workflow_id, created_at)
violations(tenant_id, run_id, contract_code)
repair_patches(tenant_id, violation_id)
regression_tests(tenant_id, violation_id)
trace_events(tenant_id, run_id, step)
tool_events(tenant_id, run_id, tool_name)
```

## 6. FalkorDB graph schema

Use FalkorDB for topology, contract relationships, and recurrence memory.

### Nodes

```text
(:Tenant {id, name})
(:Workflow {id, name, framework})
(:Agent {id, name, type})
(:Tool {id, name, type})
(:Contract {id, code, type, severity})
(:Run {id, status, created_at})
(:TraceEvent {id, step, type, timestamp})
(:Violation {id, code, severity})
(:RepairPatch {id, affected_primitive})
(:RegressionTest {id, status})
(:Document {id, source_type, uri})
(:Pattern {id, fingerprint, count})
```

### Relationships

```text
(:Tenant)-[:OWNS]->(:Workflow)
(:Workflow)-[:HAS_AGENT]->(:Agent)
(:Workflow)-[:HAS_TOOL]->(:Tool)
(:Workflow)-[:HAS_CONTRACT]->(:Contract)
(:Workflow)-[:HAS_RUN]->(:Run)
(:Run)-[:HAS_EVENT]->(:TraceEvent)
(:Run)-[:HAS_VIOLATION]->(:Violation)
(:Violation)-[:VIOLATES]->(:Contract)
(:Violation)-[:FAILED_AT]->(:TraceEvent)
(:Violation)-[:INVOLVES_AGENT]->(:Agent)
(:Violation)-[:REPAIRED_BY]->(:RepairPatch)
(:RepairPatch)-[:VALIDATED_BY]->(:RegressionTest)
(:Agent)-[:HANDOFF_TO]->(:Agent)
(:Agent)-[:USES_TOOL]->(:Tool)
(:Violation)-[:MATCHES_PATTERN]->(:Pattern)
(:Document)-[:DECLARES_INTENT_FOR]->(:Workflow)
```

### Example graph queries

Find recurring violations:

```cypher
MATCH (w:Workflow {id: $workflow_id})-[:HAS_RUN]->(r:Run)-[:HAS_VIOLATION]->(v:Violation)
RETURN v.code, v.affected_primitive, count(*) AS count
ORDER BY count DESC
```

Find unsafe path to ActionAgent:

```cypher
MATCH p = (a:Agent {name: "ReporterAgent"})-[:HANDOFF_TO*1..3]->(b:Agent {name: "ActionAgent"})
WHERE NONE(n IN nodes(p) WHERE n.name = "HumanGate")
RETURN p
```

## 7. API contract

### POST /api/workflows

Request:

```json
{
  "name": "Literature Review Assistant",
  "framework": "ag2",
  "topology": {},
  "contracts": []
}
```

Response:

```json
{
  "workflow_id": "wf_123",
  "status": "created"
}
```

### POST /api/runs

Request:

```json
{
  "workflow_id": "wf_123",
  "trace": {},
  "final_output": {},
  "mode": "analyze_trace"
}
```

Response:

```json
{
  "run_id": "run_123",
  "status": "queued"
}
```

### GET /api/runs/{run_id}

Response includes:

- run metadata
- normalized trace
- violations
- repairs
- regression tests
- report
- cost data

### GET /api/runs/{run_id}/events

Use WebSocket or SSE.

Event examples:

```json
{"type": "RUN_STARTED", "run_id": "run_123"}
{"type": "TRACE_NORMALIZED", "event_count": 42}
{"type": "VIOLATION_FOUND", "violation_id": "v_123", "code": "C-EVD"}
{"type": "REPAIR_GENERATED", "repair_id": "repair_123"}
{"type": "TEST_PASSED", "test_id": "test_123"}
{"type": "REPORT_READY", "run_id": "run_123"}
```

## 8. AG2 pattern usage

| Product area | AG2 feature | Use |
|---|---|---|
| Diagnostic orchestration | GroupChat / GroupChatManager | Multi-agent diagnostic pipeline |
| Stable stage flow | RoundRobin or deterministic sequential orchestration | Reliable baseline |
| Contract routing repairs | Handoffs / OnContextCondition | Generate AG2-native routing patches |
| Shared state checks | ContextVariables | Validate workflow state requirements |
| Safety checks | RegexGuardrail and output guardrails | Catch missing citations, schema issues, unsafe output |
| Human approval | UserProxyAgent | Gate repair approval |
| Tool evidence | TavilySearchTool | External evidence verification |
| Test validation | DaytonaCodeExecutor | Run tests in sandbox |
| Live dashboard | AG-UI or custom SSE/WebSocket | Stream agent and tool events |
| Native traces | autogen.opentelemetry | Replace hand-rolled trace capture |
| Graph memory | FalkorDB GraphRAG | Workflow topology and recurrence memory |

## 9. Deployment topology

### Local development

```text
frontend dev server
FastAPI API server
worker process
SQLite
optional FalkorDB Docker container
optional Daytona cloud sandbox
```

### Pilot deployment

```text
Vercel or frontend host
API container
worker container
Postgres
FalkorDB
Redis queue
Daytona cloud
Tavily API
Gemini/OpenRouter
```

### Production target

```text
CDN / frontend
API service
worker service
Postgres primary
FalkorDB graph store
Redis / queue
object storage for trace archives
secrets manager
observability backend
Daytona sandbox pool
```

## 10. Security model

### Authentication

P0:

- API key per tenant.

P1:

- dashboard login.
- SSO for pilots if required.

### Authorization

Every request resolves:

```text
api_key -> tenant_id -> allowed workflow/run access
```

No cross-tenant reads.

### Secrets

Never store raw API keys.

Store:

- hash of Concord API key
- encrypted external provider keys if users supply them
- environment-managed Daytona/Tavily/Gemini keys for internal runs

### Trace privacy

Traces can contain sensitive prompts, documents, or tool outputs.

Policies:

- raw trace storage optional per tenant
- redaction hooks before persistence
- sensitive keys never written to trace
- UI labels fixture vs live data

### Sandbox safety

Daytona is preferred for executing generated regression tests.

Rules:

- no local execution of untrusted generated code in production
- timeout on every execution
- resource limits
- cleanup after execution
- captured stdout/stderr only
- no secrets in sandbox unless explicitly required

### Repair safety

Repairs are recommendations by default.

No automatic patch application in v1.0 without human approval.

## 11. Reliability model

Every LLM call must have a deterministic fallback.

Every contract verdict must be reproducible.

Every repair must name an affected primitive.

Every generated test must include assertions.

Every report must cite trace evidence.

If a tool fails, report status should say:

```text
tool_status = failed
verdict_source = deterministic_check
tool_evidence = unavailable
```

Do not silently downgrade failed tools to success.
