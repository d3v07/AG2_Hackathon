# Concord v1 Plan vs Reality

Status date: 2026-06-01

This is the current north-star scorecard for Concord v1. It supersedes the May 6 audit snapshot in `docs/NEXT_PHASE_AUDIT.md`, which is preserved as historical evidence for #12.

## North Star

Concord is an AG2-first contract-to-repair platform. A developer registers a workflow contract, submits a run or trace, receives deterministic contract violations with AG2 primitive attribution, gets one repair patch per violation, validates the repair in Daytona, exports the report, and can revisit persisted run history.

Concord is not a generic tracing dashboard, no-code builder, or broad observability clone. Traces and spans exist to support the repair loop, not as the product by themselves.

## Current Product Loop

| Step | Status | Evidence |
|---|---|---|
| Create API key | PASS | Backend key route and status probe: `api/routes/api_keys.py`; product UI API Access panel: `public/app.jsx`; first-key bootstrap docs: `docs/ONBOARDING.md`. |
| Register workflow contract | PASS | `POST /api/workflows` accepts normalized JSON and YAML contract DSL: `api/routes/workflows.py`, `zone_b/contracts/parser.py`. |
| Submit task or trace | PASS | `POST /api/runs` accepts task specs/raw traces: `api/routes/runs.py`; product form submits real-run payloads: `public/app.jsx`. |
| Collect AG2 trace/spans | PASS | Zone A instrumentation and SDK exporter are implemented in `zone_a/trace_adapter.py` and `sdk/`. |
| Detect deterministic violations | PASS | Five default contract types live in `zone_b/contracts/registry.py`: evidence, tool, routing, approval, schema. |
| Attribute failed primitive | PASS | Attribution output is assembled in `zone_b/agents/attribution.py` and linked into reports/dashboard rows. |
| Emit per-violation repairs | PASS | `zone_b/agents/repair.py` emits `patches[]`; `api/adapter.py` passes native patches through when present. |
| Validate repair in Daytona | PASS, credential-gated | `zone_b/agents/regression_test.py` uses `DaytonaCodeExecutor` through `zone_b/sandbox/runner.py`; invalid or missing credentials return explicit validation states rather than fake passes. |
| Persist history and usage | PASS | SQLModel-backed persistence and tenant queries are in `api/store.py`, `api/models.py`, and `api/routes/runs.py`. |
| Export completed report | PASS | `EXPORT JSON` builds a complete report payload in `public/app.jsx`. |

## Deliberate Demo Boundary

The Literature Review Assistant is the bundled demo workflow. It is not Concord's product boundary. Zone B is workflow-agnostic as long as traces match the shared model and contracts are registered.

`stub` and fixture paths are internal verification/demo paths. The public product path defaults to real task submission and honest validation states.

## Remaining Recovery Issues

| Issue | Purpose |
|---|---|
| #142 | Consolidate active docs around this scorecard and remove stale contradictions. |
| #143 | Archive orphaned Lite/prototype artifacts only after reference checks prove they are unused. |
| #144 | Produce the final end-to-end demo script for register -> run -> violation -> repair -> Daytona validation -> export -> history. |
