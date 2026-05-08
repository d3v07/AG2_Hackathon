# /go State

## Overview
- Project: Concord Lite / Concord v1.0
- Mode: safe
- Phase: Sprint 7 ready to land
- Branch: feat/sprint-7-live-dashboard
- Current Sprint: Sprint 7
- Current Task: #24-#26 live run events, dashboard LIVE/FIXTURE mode, and SSE badge
- Last Checkpoint: Sprint 7 reviewer findings were addressed and the current tree passed focused tests, full pytest, fixture pipeline, OTel spike, repo-valid import smoke, local tokenized SSE probe, deployed demo probe, diff check, and browser QA.

## Sprint Board
Sprint 3: Foundation
- #12 P0 Docs: Audit current state and write NEXT_PHASE_AUDIT.md — closed on `main`
- #13 P0 Zone B: Add C-RTE Routing contract as deterministic lambda — closed on `main`
- #14 P0 Zone B: Add C-SCH Schema contract as deterministic lambda — closed on `main`

Sprint 4: Repair and downstream report compatibility
- #15 P0 Zone B: Replace primary-only repair generation with one patch per violation — closed on `main`
- #16 P0 Zone B: Generate per-violation regression outcomes — closed on `main`
- #17 P0 API: Pass backend report patches through to dashboard data — closed on `main`

Sprint 5: API persistence and run APIs
- #18 P0 API: Add SQLite + SQLModel persistence layer — closed on `main`
- #19 P0 API: Implement POST /api/workflows + listing endpoints — closed on `main`
- #20 P0 API: Implement POST /api/runs with status state machine — closed on `main`

Sprint 6: AG2 tracing and SDK
- #21 P0 Zone A: Verify AG2 OpenTelemetry import paths and document them — closed on `main`
- #22 P0 Zone A: Add OTel span-to-RunTrace exporter — closed on `main`
- #23 P0 SDK: Add one-line instrumentation and API client package — closed on `main`

Sprint 7: Live run events and dashboard mode controls
- #24 P0 API: Add in-process SSE event bus and `/api/runs/{id}/events`
- #25 P0 Dashboard: Wire live updates from SSE while keeping fixture mode default
- #26 P0 Dashboard: Add LIVE/FIXTURE toggle and badge

## What Worked
- GitHub issues #12-#15 are closed on `main`.
- Branch `feat/sprint-3-foundation` was created from a clean local `production` worktree.
- Initial audit: `pytest -x --tb=short` passed 275 tests, 3417 warnings, 133.62s.
- Regression gate stabilization added deterministic fallback rerun for bad generated tests.
- Post-fix: `pytest -x --tb=short` passed 277 tests, 3417 warnings, 206.54s.
- Post-fix: `python3 run_all.py --fixture` printed a report with `Regression status : pass`.
- Post-fix: `pytest tests/test_integration.py::TestRunAllFixtureMode -q` passed 4 tests.
- Live demo returned HTTP 200.
- AG2 core, handoff, Daytona executor, and Tavily tool imports are available.
- #13 RED tests failed for the expected reason before implementation: no routing contract existed.
- #13 routing contract now fails the fixture trace, passes a clean ordered trace, and rejects a Verifier tool id without a successful tool event.
- Deterministic regression fallback now covers the routing invariant as well as evidence/tool/approval.
- Fixture pipeline now reports 4 violations with severity summary `{'high': 3, 'medium': 1, 'low': 0}`.
- #13 focused gate passed: `pytest tests/test_routing_contract.py tests/test_contract_checker.py tests/test_rigorous.py::TestPartialContractFailures tests/test_regression_test.py -q` passed 55 tests.
- #13 fixture gate passed: `python3 run_all.py --fixture` reported `Regression status : pass`.
- #13 integration gate passed: `pytest tests/test_integration.py::TestContractViolationDetection tests/test_integration.py::TestRunAllFixtureMode tests/test_group_chat.py -q` passed 22 tests.
- #13 full gate passed: `pytest -x --tb=short` passed 281 tests.
- #13 live demo probe returned HTTP 200.
- #14 RED tests failed for the expected reason before implementation: no schema contract existed.
- #14 schema contract now enforces required `final_output` keys from `ContextSnapshot.final_output`.
- #14 keeps fixture C-SCH passing and fixture violation count at 4.
- Deterministic regression fallback now covers schema as well as evidence/tool/routing/approval.
- #14 focused gate passed: `pytest tests/test_schema_contract.py tests/test_contract_checker.py tests/test_regression_test.py tests/test_rigorous.py::TestPartialContractFailures -q` passed 59 tests.
- #14 fixture gate passed: `python3 run_all.py --fixture` reported `Regression status : pass`.
- #14 integration gate passed: `pytest tests/test_schema_contract.py tests/test_contract_checker.py tests/test_integration.py::TestContractViolationDetection tests/test_integration.py::TestRunAllFixtureMode tests/test_group_chat.py -q` passed 54 tests.
- #14 full gate passed: `pytest -x --tb=short` passed 288 tests.
- #14 live demo probe returned HTTP 200.
- #14 review pass found no blocking issues.
- #15 RED repair tests failed for the expected reason before implementation: `run_repair` did not return `patches`.
- #15 repair now emits one patch per violation while preserving scalar aliases for legacy callers.
- #15 reporter now includes `report.patches[]` while preserving existing scalar fields.
- #15 reviewer pass found no blocking issues; the non-blocking multi-patch reporter coverage note was addressed.
- #15 focused gate passed: `pytest -q tests/test_repair.py tests/test_reporter.py tests/test_group_chat.py tests/test_integration.py` passed 66 tests.
- #15 full gate passed: `pytest -x --tb=short` passed 294 tests.
- #15 fixture gate passed: `python3 run_all.py --fixture` reported `Repair patches    : 4`, `Regression status : pass`, and `Approval status   : approved`.
- #15 AG2 import smoke passed.
- #15 live demo probe returned HTTP 200.
- #15 `git diff --check` passed.
- Public landing path approved: push `feat/sprint-3-foundation`, open PR to `production`, run review/check gate, merge only if clean, verify `production`, then open and check PR from `production` to `main`.
- PR #42 merged `feat/sprint-3-foundation` into `production`.
- PR #43 merged `production` into `main`.
- #16 is open and depends only on #15.
- #16 RED tests failed for the expected reason before implementation: regression output lacked `per_violation_results`, reporter output lacked `regression_summary`, and fixture output lacked the per-violation regression count.
- #16 regression now emits one `per_violation_results[]` row per violation plus `per_violation_summary`.
- #16 reporter now adds `test_status` to each violation and includes `regression_tests[]` plus `regression_summary`.
- #16 focused gate passed: `pytest -q tests/test_per_violation_repairs.py tests/test_regression_test.py tests/test_reporter.py tests/test_group_chat.py tests/test_integration.py tests/test_rigorous.py::TestFallbackTestGeneration` passed 73 tests.
- #16 full gate passed: `pytest -x --tb=short` passed 298 tests.
- #16 fixture gate passed: `python3 run_all.py --fixture` reported `Regression tests   : 4 pass / 0 fail / 0 error`.
- #16 AG2 import smoke passed.
- #16 live demo probe returned HTTP 200.
- #16 `git diff --check` passed.
- User steered the active Sprint 4 run to continue after an interrupted focused test wait.
- #17 RED adapter test failed for the expected reason: `api/adapter.py` still used template primitives instead of backend `report.patches[]`.
- #17 adapter now passes native backend repair patches through to dashboard `CONCORD_DATA.patches[]` when present, while preserving legacy scalar patch synthesis when `report.patches` is absent.
- #17 seeded dashboard fixture compatibility is covered through `api.store.get_run("RUN-041")`.
- #17 targeted gate passed: `pytest tests/test_api_adapter_multi_patch.py -q` passed 3 tests.
- #17 focused gate passed: `pytest -q tests/test_api_adapter_multi_patch.py tests/test_per_violation_repairs.py tests/test_repair.py tests/test_reporter.py tests/test_integration.py` passed 61 tests.
- #17 full gate passed: `pytest -x --tb=short` passed 301 tests.
- #17 fixture gate passed: `python3 run_all.py --fixture` reported `Repair patches    : 4`, `Regression status : pass`, and `Regression tests   : 4 pass / 0 fail / 0 error`.
- #17 `git diff --check` passed.
- #17 AG2 import smoke passed using repo-valid group chat, handoff, guardrail, Daytona executor, and Daytona SDK import paths.
- #17 live API probe passed after starting `.venv/bin/uvicorn api.index:app --port 8765`: `GET /api/runs/RUN-041` returned HTTP 200 with 4 patches.
- PR #44 merged Sprint 4 into `production`; PR #45 merged `production` into `main`.
- GitHub issues #16 and #17 are closed on `main`.
- Sprint 5 branch `feat/sprint-5-api-persistence` was created from updated `production`.
- #18/#19/#20 RED tests failed for the expected reason before implementation: `api.db`, `api.models`, persistence-backed store, workflow routes, and run submission routes were missing.
- API dependencies were pinned to Python 3.14-compatible versions: FastAPI 0.136.1, Pydantic 2.13.4, SQLModel 0.0.38.
- #18 now stores workflows, runs, violations, patches, and tests in SQLite-backed SQLModel records with `tenant_id` on every table.
- #19 now supports `POST /api/workflows`, `GET /api/workflows`, and `GET /api/workflows/{workflow_id}` with deterministic contract schema validation.
- #20 now supports `POST /api/runs`, `GET /api/runs/{run_id}/status`, and status history `queued -> analyzing -> completed|failed`.
- Sprint 5 targeted gate passed: `pytest tests/test_api_persistence.py tests/test_api_workflows.py tests/test_api_runs.py -q` passed 11 tests.
- Sprint 5 focused gate passed: `pytest -q tests/test_api_persistence.py tests/test_api_workflows.py tests/test_api_runs.py tests/test_api_adapter_multi_patch.py tests/test_integration.py` passed 34 tests.
- Operator steering: use multiple agents for subsequent sprint work where they can reduce risk, and continue the branch -> `production` -> `main` landing loop after each sprint before starting the next sprint.
- Operator steering: read automated review comments on recent PRs and apply any critical changes before landing the active sprint.
- Sprint 5 review blockers were addressed: API routes now pass authenticated non-local tenant context into storage and background processing, queued/analyzing runs are marked failed during API startup recovery, and approval updates preserve status history.
- Sprint 5 regression gate is stable in pytest via `CONCORD_REGRESSION_RUNNER=local`; the direct `python3 run_all.py --fixture` gate still exercises the live sandbox path and passed.
- Sprint 5 focused review gate passed: `pytest -q tests/test_api_persistence.py tests/test_api_workflows.py tests/test_api_runs.py tests/test_api_adapter_multi_patch.py tests/test_per_violation_repairs.py tests/test_regression_test.py tests/test_contract_checker.py tests/test_reporter.py tests/test_integration.py` passed 114 tests.
- Sprint 5 full gate passed: `pytest -x --tb=short` passed 328 tests.
- Sprint 5 fixture gate passed: `python3 run_all.py --fixture` reported `Repair patches    : 4`, `Regression status : pass`, and `Regression tests   : 4 pass / 0 fail / 0 error`.
- Sprint 5 `git diff --check` passed.
- Sprint 5 AG2 import smoke passed.
- Sprint 5 local API probe passed: `GET /api/health` returned 200, `GET /api/runs/RUN-041` returned 4 patches with `completed`, and unauthenticated `X-Tenant-ID: tenant-a` was rejected with 401.
- PR #46 inline comments were addressed locally with tests: local regression runner errors report `error`, JSONP escapes JS-sensitive output, API startup uses explicit store initialization, and reporter summary naming now matches per-violation status semantics.
- PR #46 merged Sprint 5 into `production`; PR #47 merged `production` into `main`.
- GitHub issues #18, #19, and #20 are closed on `main`.
- Sprint 6 branch `feat/sprint-6-ag2-sdk` was created from updated `production`.
- #21 verified `autogen.opentelemetry` imports for `instrument_agent`, `instrument_llm_wrapper`, and `instrument_pattern`; HTTP OTLP and in-memory exporter paths were documented in `docs/AG2_VERSIONING.md`.
- #21 spike `python3 scripts/otel_spike.py` passed and printed a native AG2 tool span plus its normalized Concord event.
- #22 added `zone_a.trace_adapter.ConcordSpanExporter` and tests for raw-trace round trip, native AG2 agent/tool spans, handoff derivation, malformed spans, malformed context JSON, and ordering.
- #23 added standalone `sdk/` package with `ConcordClient`, one-line `instrument()`, server-side tenant headers, editable install smoke, and SDK submission tests.
- Sprint 6 first reviewer found two blocking issues: SDK imported `zone_a` and exporter dropped native AG2 spans without Concord attributes. Both were fixed with package-local adapter and native `ag2.span.type`/`gen_ai.*` mapping.
- Sprint 6 second reviewer found two follow-up blockers: `complete()` discarded captured native spans and repo-local context JSON parsing could drop malformed spans. Both were fixed; `complete()` now prefers captured spans and raw-trace replay is fallback only.
- Sprint 6 final reviewer found two more blockers: clean SDK install lacked the AG2 provider extra needed by the Zone A spike, and repeated `complete()` calls could resubmit prior spans. Both were fixed with `ag2[openai]` dependencies and a regression test that proves submitted spans are cleared per run.
- Sprint 6 focused gate passed: `pytest -q tests/test_otel_exporter.py tests/test_sdk_instrumentation.py tests/test_swarm.py tests/test_api_runs.py tests/test_integration.py` passed 73 tests.
- Sprint 6 full gate passed: `pytest -x --tb=short` passed 343 tests.
- Sprint 6 fixture gate passed: `python3 run_all.py --fixture` reported `Regression status : pass` and `Regression tests   : 4 pass / 0 fail / 0 error`.
- Sprint 6 SDK install/spike smoke passed in a fresh temporary venv with `python3 -m pip install -e ./sdk`, `import concord_sdk`, and `python3 scripts/otel_spike.py`.
- Sprint 6 `git diff --check` passed.
- Sprint 6 AG2/OTel import smoke passed.
- Sprint 6 local API probe passed: `GET /api/health` returned 200, `GET /api/runs/RUN-041` returned 4 patches with `completed`, and unauthenticated `X-Tenant-ID: tenant-a` was rejected with 401.
- PR #48 merged Sprint 6 into `production`; PR #49 merged `production` into `main`.
- GitHub issues #21, #22, and #23 are closed on `main`.
- Operator steering: use multiple agents for Sprint 7 discovery/review while the main lane owns final implementation and gate execution.
- Sprint 6 post-main verification passed locally: `pytest -x --tb=short` passed 343 tests, `python3 run_all.py --fixture` passed, `python3 scripts/otel_spike.py` passed, local API probe passed, and issues #21-#23 are closed.
- Merged Sprint 6 branch `feat/sprint-6-ag2-sdk` was deleted locally and remotely after landing on `main`.
- Sprint 7 branch `feat/sprint-7-live-dashboard` was created from updated `production`.
- #24 added `api.events` process-local run event bus and `GET /api/runs/{run_id}/events` using FastAPI `EventSourceResponse`, tenant-scoped by run and tenant.
- #24 event stream replays persisted `queued -> analyzing -> completed|failed` status history, honors `Last-Event-ID`, closes on terminal runs, and supports short-lived stream tokens for browser EventSource authentication.
- #25 keeps fixture mode as the dashboard default and adds LIVE mode that fetches `GET /api/runs/{id}`, obtains `/events/token`, and listens to `/events?stream_token=...`.
- #25 adapter now derives observed `topology` and `routes` from actual run traces for live dashboard payloads so the Workflow DAG does not depend on fixture-only fields.
- #26 added the topbar FIXTURE/LIVE segmented control plus persistent source badge and source meta cell.
- Sprint 7 targeted gate passed: `pytest -q tests/test_api_run_events.py tests/test_api_adapter_multi_patch.py tests/test_dashboard_live_mode.py tests/test_api_runs.py tests/test_api_workflows.py tests/test_integration.py` passed 48 tests.
- Sprint 7 full gate passed: `pytest -x --tb=short` passed 351 tests.
- Sprint 7 fixture gate passed: `python3 run_all.py --fixture` reported `Regression status : pass` and `Regression tests   : 4 pass / 0 fail / 0 error`.
- Sprint 7 AG2/FastAPI import smoke passed, including `EventSourceResponse`, `ServerSentEvent`, and `ConcordSpanExporter`.
- Sprint 7 OTel spike passed: `python3 scripts/otel_spike.py`.
- Sprint 7 `git diff --check` passed.
- Sprint 7 local API/SSE probe passed: health 200, `GET /api/runs/RUN-041` returned completed with 4 patches and 7 routes, `/events` returned `text/event-stream`, and unauthenticated non-local tenant events were rejected with 401.
- Sprint 7 browser QA passed in the in-app browser: fixture default, LIVE toggle, Workflow DAG view, mobile-width fixture/live toggle, and no console errors.
- Sprint 7 reviewer blockers were addressed: non-local browser SSE auth now uses stream tokens, SSE replay filters by sequence, arbitrary live runs no longer get fixture topology, dynamic agents/topology render without hardcoded fixture maps, and in-progress live runs avoid fixture backfill.
- Sprint 7 reviewer follow-ups were addressed: LIVE reconnect obtains a fresh stream token after errors and the pipeline graph advances to the new end state when live traces have more steps than the fixture.
- Sprint 7 final focused gate passed: `pytest -q tests/test_dashboard_live_mode.py tests/test_api_run_events.py tests/test_api_adapter_multi_patch.py` passed 20 tests.
- Sprint 7 final full gate passed: `pytest -x --tb=short` passed 359 tests.
- Sprint 7 final fixture gate passed: `python3 run_all.py --fixture` reported `Regression status : pass` and `Regression tests   : 4 pass / 0 fail / 0 error`.
- Sprint 7 final OTel spike passed: `python3 scripts/otel_spike.py`.
- Sprint 7 final repo-valid import smoke passed for AG2 agents/patterns, FastAPI SSE response, event bus/token store, Daytona SDK, and Concord span exporter.
- Sprint 7 final local API probe passed: health 200, `GET /api/runs/RUN-041` returned completed with 4 patches and 7 routes, `/events/token` issued a token, `/events?stream_token=...` replayed through sequence 3, and unauthenticated non-local tenant events returned 401.
- Sprint 7 deployed demo probe returned HTTP 200.
- Sprint 7 final browser QA passed with gstack browse: desktop and mobile fixture defaults, LIVE reaches `LIVE COMPLETED`, DAG renders, mobile has no horizontal document overflow, and the only console warning is the existing in-browser Babel warning.

## What Did Not Work
- Initial audit: `python3 run_all.py --fixture` exited 0 and printed a report, but the report said `Regression status : fail`.
- `python3 -m ruff check .` failed because `ruff` is not installed.
- Older FastAPI/Pydantic pins failed to install on Python 3.14 because `pydantic-core==2.23.4` only supports through Python 3.13.
- Sprint 5 focused gate initially exposed a flaky pytest fixture path that depended on live sandbox execution; fixed by adding an explicit local regression runner for subprocess tests while preserving the live direct fixture gate.
- Sprint 6 initial SDK packaging did not work outside the monorepo because `concord_sdk` imported `zone_a`; fixed with a packaged SDK trace adapter and installed-package smoke test.
- Sprint 6 initial native span support still required Concord attributes; fixed with native AG2 `gen_ai.*` mapping and tests.
- Sprint 6 clean SDK install initially missed the provider extra required by the Zone A spike; fixed by declaring `ag2[openai]>=0.12`.
- Sprint 6 reusable SDK sessions initially leaked prior spans into later submissions; fixed by resetting submitted span buffers after each `complete()`.
- `docs/PLAN_VS_REALITY.md` is referenced by the handoff but missing locally.

## Blockers
- No regression-gate blocker remains for Sprint 3.
- No #15 blocker remains.
- No #16/#17 blocker remains.
- No Sprint 5 blocker remains.
- No Sprint 6 blocker remains.
- No Sprint 7 blocker remains; final reviewer medium findings were fixed locally.
- Remaining toolchain gaps: `ruff` unavailable in the current Python environment; `docs/PLAN_VS_REALITY.md` missing.

## Exact Next Step
Commit Sprint 7 with `Closes #24`, `Closes #25`, and `Closes #26`, push PR to `production`, merge through `production` and `main`, verify `main`, delete the merged sprint branch, then start Sprint 8 (#27-#29).
