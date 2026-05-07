# /go State

## Overview
- Project: Concord Lite / Concord v1.0
- Mode: safe
- Phase: Sprint 5 landing
- Branch: feat/sprint-5-api-persistence
- Current Sprint: Sprint 5
- Current Task: #18-#20 API persistence, workflow registration, and run submission
- Last Checkpoint: Sprint 5 full verification gate passed locally.

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
- #18 P0 API: Add SQLite + SQLModel persistence layer — full gate passed locally
- #19 P0 API: Implement POST /api/workflows + listing endpoints — full gate passed locally
- #20 P0 API: Implement POST /api/runs with status state machine — full gate passed locally

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
- Sprint 5 focused review gate passed: `pytest -q tests/test_api_persistence.py tests/test_api_workflows.py tests/test_api_runs.py tests/test_api_adapter_multi_patch.py tests/test_per_violation_repairs.py tests/test_regression_test.py tests/test_contract_checker.py tests/test_reporter.py tests/test_integration.py` passed 112 tests.
- Sprint 5 full gate passed: `pytest -x --tb=short` passed 326 tests.
- Sprint 5 fixture gate passed: `python3 run_all.py --fixture` reported `Repair patches    : 4`, `Regression status : pass`, and `Regression tests   : 4 pass / 0 fail / 0 error`.
- Sprint 5 `git diff --check` passed.
- Sprint 5 AG2 import smoke passed.
- Sprint 5 local API probe passed: `GET /api/health` returned 200, `GET /api/runs/RUN-041` returned 4 patches with `completed`, and unauthenticated `X-Tenant-ID: tenant-a` was rejected with 401.

## What Did Not Work
- Initial audit: `python3 run_all.py --fixture` exited 0 and printed a report, but the report said `Regression status : fail`.
- `python3 -m ruff check .` failed because `ruff` is not installed.
- Older FastAPI/Pydantic pins failed to install on Python 3.14 because `pydantic-core==2.23.4` only supports through Python 3.13.
- Sprint 5 focused gate initially exposed a flaky pytest fixture path that depended on live sandbox execution; fixed by adding an explicit local regression runner for subprocess tests while preserving the live direct fixture gate.
- `docs/PLAN_VS_REALITY.md` is referenced by the handoff but missing locally.

## Blockers
- No regression-gate blocker remains for Sprint 3.
- No #15 blocker remains.
- No #16/#17 blocker remains.
- No Sprint 5 blocker remains.
- Remaining toolchain gaps: `ruff` unavailable in the current Python environment; `docs/PLAN_VS_REALITY.md` missing.

## Exact Next Step
Review the Sprint 5 diff, commit locally with `Closes #18`, `Closes #19`, and `Closes #20`, then land through `production` and `main` before starting Sprint 6. Use child agents for parallel review/research on later sprints after Sprint 5 lands.
