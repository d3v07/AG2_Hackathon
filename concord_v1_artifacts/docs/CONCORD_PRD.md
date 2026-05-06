# Concord PRD

## 1. Product summary

Concord is an AG2-first contract-to-repair platform for multi-agent workflows.

It watches a multi-agent workflow run, checks the run against explicit workflow contracts, detects contract violations, maps each violation to the affected workflow primitive, recommends a repair patch, validates the repair through a regression test, and stores the result for future prevention.

Concord Lite proved the concept in a hackathon. Concord v1.0 turns it into a real developer tool.

## 2. Product thesis

Agent frameworks make it easier to build multi-agent workflows. They do not fully solve workflow correctness.

Developers still need to know:

- Did the workflow follow its declared contract?
- Did the right agents run in the right order?
- Did agents use the tools they claimed to use?
- Did the final answer have required evidence?
- Did side effects require approval?
- What exact primitive should be changed?
- What test prevents this from happening again?

Concord exists to answer those questions.

## 3. What Concord is not

Concord is not a generic chatbot.

Concord is not a generic observability dashboard.

Concord is not a replacement for AG2 Failure Attribution.

Concord is not a no-code workflow builder.

Concord is not trying to support every multi-agent framework in v1.0.

Concord is AG2-first. The long-term architecture can support other frameworks through adapters, but v1.0 should win by being excellent for AG2 developers.

## 4. Target users

### Primary user: AG2 developer

A developer building AG2 workflows with GroupChat, handoffs, tools, guardrails, and human approval.

Pain:

- Workflows fail subtly.
- Logs are long.
- Final outputs can look correct while violating evidence or routing rules.
- Fixes are unclear.
- Regression tests are rare.

### Secondary user: AI platform engineer

A platform engineer responsible for making internal agent systems safe enough for production.

Pain:

- Multiple teams build agents differently.
- There is no central contract enforcement layer.
- They need auditability, cost visibility, and approval controls.

### Tertiary user: research automation team

A team using multi-agent workflows for literature review, lab analysis, or experiment planning.

Pain:

- Research agents can produce confident unsupported claims.
- Evidence provenance matters.
- They need repeatability and review trails.

## 5. Jobs to be done

### JTBD 1: Register workflow contracts

When I build an AG2 workflow, I want to declare the workflow's correctness rules so Concord can detect when the workflow violates them.

### JTBD 2: Submit a run

When a workflow runs, I want to send Concord the trace so Concord can inspect what happened.

### JTBD 3: Detect violations

When a run fails or produces suspicious output, I want Concord to tell me which contracts were violated.

### JTBD 4: Get a repair

When a contract is violated, I want Concord to map the violation to the concrete primitive I should change.

### JTBD 5: Generate a regression test

When Concord finds a violation, I want it to generate a test that prevents the same failure from returning.

### JTBD 6: Watch runs live

When a workflow is in progress, I want the dashboard to show agent turns, tool calls, state updates, violations, and repairs in real time.

### JTBD 7: Track recurring failures

When the same workflow violates contracts repeatedly, I want Concord to surface the pattern and recommend a systemic fix.

## 6. v1.0 scope

### P0: must ship

#### P0.1 Workflow registration

Endpoint:

```text
POST /api/workflows
```

User registers:

- workflow name
- declared topology
- agents
- tools
- contracts
- owner/team
- optional source link

Acceptance criteria:

- Workflow persists across server restart.
- Workflow has unique ID.
- Workflow can be fetched and listed.
- Contract schema validates on create.

#### P0.2 Run submission

Endpoint:

```text
POST /api/runs
```

User submits:

- workflow ID
- raw trace
- final output
- ContextVariables snapshot
- tool events
- optional task spec

Acceptance criteria:

- Run persists.
- Run is associated with workflow.
- Run status transitions through queued, analyzing, completed, failed.
- Run can be fetched.

#### P0.3 Deterministic contract engine

Supported contracts:

- Evidence contract
- Tool contract
- Routing contract
- Approval contract
- Schema contract

Acceptance criteria:

- Contract verdicts are deterministic.
- LLM is not required for the verdict.
- LLM may explain the verdict.
- Routing and Schema contracts are enforced, closing the Lite gap.

#### P0.4 Per-violation repair patches

Each violation gets its own repair patch.

Repair patch contains:

- affected primitive
- patch summary
- before/after
- suggested code or config
- confidence
- expected impact
- human approval requirement

Acceptance criteria:

- No single primary-patch limitation.
- Dashboard shows real per-violation patches.

#### P0.5 Regression test generation

Each violation gets a regression test.

Test contains:

- test name
- assertions
- code
- expected failure on broken trace
- expected pass after patch or simulated patch

Acceptance criteria:

- Test can run locally or through Daytona.
- If Daytona is unavailable, simulated fallback is explicit.

#### P0.6 Daytona validation

Use Daytona for sandboxed validation.

Acceptance criteria:

- At least one generated regression test runs in Daytona.
- Report includes pass/fail, stdout, stderr, and sandbox metadata.
- Sandbox cleanup is reliable.

#### P0.7 API-backed dashboard

Dashboard must not stay fixture-only.

Screens:

- overview
- workflow topology
- agent trace
- violations
- repair patch
- regression test
- final report

Acceptance criteria:

- Dashboard can load a real run by run ID.
- Fixture mode remains for demos.
- UI clearly distinguishes live vs fixture data.

#### P0.8 Persistent storage

Use relational storage for product data.

Local dev:

- SQLite acceptable.

Production target:

- Postgres.

Acceptance criteria:

- Workflows, runs, contracts, violations, repairs, tests, and tool events persist.

### P1: should ship shortly after v1.0

- Native AG2 tracing ingestion.
- Concord SDK.
- Live dashboard streaming through SSE/WebSocket or AG-UI adapter.
- FalkorDB workflow graph.
- Recurring violation memory.
- Repair-test-iterate loop.
- Slack/Discord/email notifications for approvals.
- Cost dashboard.
- Contract DSL in YAML.

### P2: later

- DocAgent-assisted contract extraction from design docs.
- WebSurfer-assisted external verification.
- AG2 Studio import/export or contract visualization.
- A2A remote-agent trust and agent passports.
- LangGraph adapter.
- Contract pack marketplace.
- Advanced repair ranking using ReasoningAgent.

## 7. Non-goals

Not v1.0:

- Supporting every multi-agent framework.
- No-code workflow builder.
- Full LangSmith/AgentOps replacement.
- Fully automatic patch application.
- Enterprise SSO beyond a basic design.
- Voice approval through Twilio.

Avoid:

- Claims that Concord replaces AG2 Failure Attribution.
- Claims that agents are always right.
- Claims that repairs are safe without human approval.
- Building broad observability instead of contract verification.

## 8. Success metrics

Product metrics:

- First workflow registered and analyzed in under 10 minutes.
- 90% of runs produce a complete report.
- 95% deterministic contract verdict reproducibility.
- 80% of generated regression tests syntactically valid.
- 50% of patches copied, approved, or used by early users.

Developer metrics:

- SDK integration under 10 lines.
- Local setup under 15 minutes.
- First run visible in dashboard under 2 minutes after submission.

Reliability metrics:

- No tenant isolation failures in tests.
- No unapproved side-effect patch application.
- Daytona sandbox cleanup success above 99%.
- Every violation links to trace evidence.

## 9. v1.0 launch criteria

Concord v1.0 is ready when a developer can:

1. Create an API key.
2. Register an AG2 workflow.
3. Submit a trace or run task.
4. See live run status.
5. View contract violations.
6. See one repair per violation.
7. Run at least one regression test in Daytona.
8. Export a report.
9. Return later and see persisted history.

## 10. Open questions

1. Should contract DSL be YAML-only in v1.0, or should Python remain first-class?
2. Should Concord store raw messages by default, or redact sensitive content?
3. How much source-code access is required for diff-grade repair patches?
4. What is the minimum viable tenant/auth model for pilots?
5. Should Daytona be required, or optional with local fallback?
6. Should FalkorDB be required for v1.0 or P1?
7. What contract packs ship by default?
