# /go State

## Overview
- Project: Concord Lite / Concord v1.0
- Mode: safe
- Phase: Sprint 4 execution
- Branch: feat/issue-16-per-violation-regression
- Current Sprint: Sprint 4
- Current Task: #16 per-violation regression test generation
- Last Checkpoint: #16 full gate passed locally; local commit recorded.

## Sprint Board
Sprint 3: Foundation
- #12 P0 Docs: Audit current state and write NEXT_PHASE_AUDIT.md — closed on `main`
- #13 P0 Zone B: Add C-RTE Routing contract as deterministic lambda — closed on `main`
- #14 P0 Zone B: Add C-SCH Schema contract as deterministic lambda — closed on `main`

Sprint 4: Repair and downstream report compatibility
- #15 P0 Zone B: Replace primary-only repair generation with one patch per violation — closed on `main`
- #16 P0 Zone B: Generate per-violation regression outcomes — full gate passed, local commit recorded
- #17 P0 API: Pass backend report patches through to dashboard data — pending

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

## What Did Not Work
- Initial audit: `python3 run_all.py --fixture` exited 0 and printed a report, but the report said `Regression status : fail`.
- `python3 -m ruff check .` failed because `ruff` is not installed.
- `api.index` import failed because `fastapi` is not installed in the current Python environment.
- `docs/PLAN_VS_REALITY.md` is referenced by the handoff but missing locally.

## Blockers
- No regression-gate blocker remains for Sprint 3.
- No #15 blocker remains.
- No #16 blocker remains.
- Remaining toolchain gaps: `ruff` unavailable, FastAPI unavailable in this Python environment, `docs/PLAN_VS_REALITY.md` missing.

## Exact Next Step
Wait for fresh approval before pushing or creating a PR for #16.
