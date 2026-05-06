# Concord: The Real Product

## 1. Why Concord exists

Concord started as Concord Lite, a hackathon prototype that proved a simple idea: a multi-agent workflow can look successful while violating the contracts that make it trustworthy.

The prototype showed one broken AG2 workflow, one diagnostic pipeline, and one final report. That was enough for a hackathon. It is not enough for a product.

The real Concord is the correctness layer for multi-agent workflows.

Concord sits above agent frameworks. It consumes traces, declared workflow contracts, tool events, state snapshots, and approval records. Then it answers five questions:

1. What contract was violated?
2. Which workflow primitive caused or allowed the violation?
3. What repair patch should be applied?
4. What regression test prevents this from recurring?
5. Has this pattern happened before?

## 2. Concord Lite vs Concord

| Dimension | Concord Lite | Concord v1.0 | Concord Platform |
|---|---|---|---|
| Goal | Win hackathon with a sharp vertical slice | Become a real AG2-first developer product | Become framework-agnostic correctness control plane |
| Workflow source | Curated Zone A Literature Review Assistant | User-registered AG2 workflows | AG2, LangGraph, CrewAI, OpenAI Agents SDK, Google ADK, A2A, MCP |
| Trace source | Fixture or local run | Native AG2 trace ingestion and POST /api/runs | Framework adapters and OpenTelemetry/OpenInference bridges |
| Storage | In-memory or fixture data | SQLite/Postgres plus run history | Postgres plus FalkorDB graph and memory layer |
| Contracts | 3 deterministic checks + declared future checks | Evidence, Tool, Routing, Approval, Schema contracts | Custom DSL, contract packs, inferred contracts |
| Repair | One primary patch | One patch per violation | Repair-test-iterate loops and patch history |
| Test | Generated demo test | Daytona-validated regression tests | AgentCI test suite and CI/CD integration |
| Dashboard | Frontend-first demo | API-backed live dashboard | Multi-tenant ops console |
| Trust model | Honest demo fallback | Deterministic checks own verdicts | Auditable, tenant-isolated, policy-governed platform |

## 3. The product boundary

Concord is not a generic tracing product.

AG2 and other frameworks already provide tracing and observability primitives. Concord uses those as input.

Concord is not AG2 Failure Attribution.

AG2 Failure Attribution asks who failed and when. Concord asks what contract broke, which primitive to repair, and what test prevents recurrence.

Concord is not a no-code workflow builder.

It does not try to replace AG2 Studio or framework-specific builders. It verifies and repairs workflows after they are designed.

Concord is not an autonomous patch applier.

Every repair is a recommendation by default. Human approval remains required before applying or exporting repairs.

## 4. The long-term platform map

The early brainstorming separated Concord into named modules:

| Earlier idea | Role inside the real Concord |
|---|---|
| Janus | Failure context and trace-to-repair support |
| Consul | Future A2A remote-agent trust and admission |
| HandoffLint | Routing contract verification |
| StateGuard | ContextVariables and shared-state contract verification |
| ToolTruth | Tool-event and tool-claim auditing |
| GuardrailGen | Failure-to-guardrail repair generation |
| AgentCI | Regression test generation and CI integration |

The key strategic correction is that these should not be seven separate products.

They are internal engines inside one loop:

```text
Trace -> Contract Violation -> Affected Primitive -> Repair Patch -> Regression Test -> Memory
```

## 5. Why the current Concord wedge is stronger

The broad platform claim is too wide for early execution.

A vague pitch says:

```text
We solve tracing, trust, routing, state, tools, guardrails, and CI.
```

A sharper Concord pitch says:

```text
This workflow violated its contract. Concord found the violated contract, identified the broken primitive, generated the repair patch, and created the regression test.
```

That is easier to build, easier to demo, and easier to sell.

## 6. The real product loop

### Step 1: Register workflow

The developer registers an AG2 workflow:

- agents
- topology
- tools
- contract rules
- approval rules
- optional source links

### Step 2: Submit run

The developer submits:

- native AG2 trace
- final output
- tool events
- ContextVariables snapshots
- approval records

### Step 3: Normalize trace

Concord converts raw trace data into a canonical RunTrace:

- agent turns
- handoffs
- tool calls
- code execution
- human input
- speaker selection
- state updates

### Step 4: Enforce contracts

Deterministic contract engine checks:

- evidence contract
- tool contract
- routing contract
- approval contract
- schema contract

### Step 5: Generate per-violation repair

Each violation gets:

- affected primitive
- before/after
- patch summary
- patch code or config
- expected impact
- approval requirement

### Step 6: Generate regression test

Each violation becomes a test:

- should fail on broken trace
- should pass after repair
- can run in Daytona or local fallback

### Step 7: Store memory

Concord stores:

- recurring violation patterns
- contract history
- repair success rate
- workflow topology
- agent/tool risk profile

### Step 8: Improve future runs

The product gradually becomes a correctness memory for agent workflows.

## 7. First user

The first user is an AG2 developer moving from demo agents to real workflows.

They have:

- a GroupChat or Swarm-like workflow
- tools
- handoffs
- shared state
- human approval points
- repeated subtle failures

They need:

- deterministic checks
- evidence-based violations
- clear repairs
- regression tests
- repeatability

## 8. Long-term product vision

Concord becomes the CI/CD and safety control plane for multi-agent workflows.

Long term, it should support:

- AG2 native tracing ingestion
- workflow contracts
- custom DSL
- repair patch generation
- Daytona sandbox validation
- live dashboard streaming
- multi-tenant run history
- FalkorDB topology and recurrence memory
- A2A remote-agent trust
- framework adapters
- CI integration
- contract packs

The full vision:

```text
Agent frameworks run workflows.
Concord verifies, repairs, and remembers them.
```

## 9. The sentence everyone should use

Concord is the contract-to-repair layer for multi-agent workflows.

It turns failed runs into violated contracts, repair patches, and regression tests.
