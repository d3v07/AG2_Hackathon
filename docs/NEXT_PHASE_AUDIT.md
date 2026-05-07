# Next Phase Audit

Audit timestamp: 2026-05-06 12:43:39 EDT

Scope: GitHub issue #12 plus the follow-up regression-gate stabilization requested after the audit surfaced a fixture smoke risk.

## Summary

- Branch: `feat/sprint-3-foundation`, created from clean local `production`.
- GitHub: issues #12 through #41 are present and open.
- Initial test baseline: `pytest -x --tb=short` exited 0 with 275 passed tests.
- Post-stabilization test baseline: `pytest -x --tb=short` exits 0 with 277 passed tests.
- Fixture pipeline: `python3 run_all.py --fixture` exits 0, prints a Contract Violation Report, and now reports `Regression status : pass`.
- Important fixture finding: the initial audit run completed but reported `Regression status : fail`; root cause was that a parseable but bad generated regression test bypassed the deterministic fallback.
- Live demo: `https://concord-lite.vercel.app/` returns HTTP 200.
- Lint gate: unavailable in the current Python environment because `ruff` is not installed.
- API import gate: unavailable in the current Python environment because `fastapi` is not installed.
- Handoff doc gap: `docs/PLAN_VS_REALITY.md` is referenced by the handoff but is missing after an earlier revert.

## Command Results

| Check | Command | Exit | Result |
|---|---|---:|---|
| Branch | `git branch --show-current` | 0 | `feat/sprint-3-foundation` |
| Working tree | `git status --short` | 0 | workflow state file and this audit doc were untracked before staging; no runtime files modified |
| Remote delta | `git log origin/main..HEAD --oneline` | 0 | 19 local commits ahead of `origin/main`; none behind |
| Initial tests | `pytest -x --tb=short` | 0 | 275 passed, 3417 warnings, 133.62s |
| Post-fix tests | `pytest -x --tb=short` | 0 | 277 passed, 3417 warnings, 206.54s |
| Initial fixture smoke | `python3 run_all.py --fixture` | 0 | Contract Violation Report printed; regression status was `fail` |
| Post-fix fixture smoke | `python3 run_all.py --fixture` | 0 | Contract Violation Report printed; regression status was `pass` |
| Fixture integration | `pytest tests/test_integration.py::TestRunAllFixtureMode -q` | 0 | 4 passed |
| Lint | `python3 -m ruff check .` | 1 | `No module named ruff` |
| Live demo | `curl -s -o /dev/null -w "%{http_code}\n" https://concord-lite.vercel.app/` | 0 | `200` |
| Required docs | existence check | 0 | all present except `docs/PLAN_VS_REALITY.md` |
| AG2 imports | import check | 0 | core, handoffs, Daytona executor, Tavily tool import successfully |
| API import | `python3 -c "import api.index"` | 0 wrapper, import failed | `ModuleNotFoundError: No module named 'fastapi'` |

## Test Status

All collected pytest tests passed in the fresh baseline run. As of the Sprint 5 local verification branch, the suite collects 328 tests.

| Test file | Collected | Status |
|---|---:|---|
| `tests/test_api_adapter_multi_patch.py` | 4 | PASS |
| `tests/test_api_persistence.py` | 5 | PASS |
| `tests/test_api_runs.py` | 11 | PASS |
| `tests/test_api_workflows.py` | 5 | PASS |
| `tests/test_attribution.py` | 10 | PASS |
| `tests/test_contract_checker.py` | 27 | PASS |
| `tests/test_group_chat.py` | 12 | PASS |
| `tests/test_human_gate.py` | 6 | PASS |
| `tests/test_integration.py` | 20 | PASS |
| `tests/test_models.py` | 21 | PASS |
| `tests/test_regression_test.py` | 23 | PASS |
| `tests/test_repair.py` | 20 | PASS |
| `tests/test_reporter.py` | 15 | PASS |
| `tests/test_per_violation_repairs.py` | 4 | PASS |
| `tests/test_rigorous.py` | 57 | PASS |
| `tests/test_routing_contract.py` | 3 | PASS |
| `tests/test_schema_contract.py` | 6 | PASS |
| `tests/test_swarm.py` | 27 | PASS |
| `tests/test_trace_collector.py` | 30 | PASS |
| `tests/test_zone_a.py` | 22 | PASS |

Warnings are dependency deprecations from `autogen.fast_depends` and `daytona_sdk` under Python 3.14. They do not fail the suite today, but they are a Python-version risk.

## Live vs Mocked

| Surface | Current status | Evidence |
|---|---|---|
| Zone A live Tavily path | Live when env is loaded; fixture mode bypasses it | `zone_a/agents/researcher.py:45-58` raises if `TAVILY_API_KEY` is absent, then calls `TavilyClient.search` |
| Zone A fixture path | Working | `run_all.py:102-107` skips Zone A and uses `zone_b/fixtures/sample_trace.json` |
| Zone B contract checker | Live | `zone_b/agents/contract_checker.py:9-88` enforces evidence/tool/approval/routing/schema |
| Zone B repair | Live per-violation backend output | `zone_b/agents/repair.py` emits `patches[]` in violation order and keeps scalar aliases for current callers |
| Zone B regression test | Live Daytona path with per-violation result rows | `zone_b/agents/regression_test.py` creates, runs, and deletes a Daytona sandbox, then emits `per_violation_results[]` |
| Dashboard fixture data | Static and demo-shaped | `api/store.py:12-133` seeds `RUN-041`; `public/data.js` also carries fixture data |
| API server import | Broken in current environment | `api/index.py:19-22` imports FastAPI, but `fastapi` is not installed |

## Integration Status

Credential names are present in `.env`; no secret values were read or copied into this document.

| Integration | Current status | Evidence |
|---|---|---|
| OpenRouter / Gemini | Configured via `.env`; live calls occurred during fixture run | `zone_a/config.py:7-17` and `zone_b/config.py` use `OPENROUTER_API_KEY`; fixture output contained model cost warnings |
| Tavily | Configured via `.env`; not called in `--fixture` mode | `zone_a/agents/researcher.py:47-58` |
| Daytona | Configured via `.env`; called in fixture run | fixture output showed sandbox `449a0bfb-c513-4d9e-8dc0-98b8c2ce714f`; regression status was `fail` |
| AG2 imports | Available | `ConversableAgent`, `UserProxyAgent`, `GroupChat`, `GroupChatManager`, `LLMConfig`, `ContextVariables`, `OnContextCondition`, `Handoffs`, `DaytonaCodeExecutor`, and `TavilySearchTool` import successfully |

## Exact v0 Gaps Remaining

1. All five declared contracts are enforced in backend code.
   - Declared workflow contract includes evidence, tool, routing, approval, and schema at `zone_a/workflow_contract.py:4-40`.
   - Backend `CONTRACTS` contains evidence, tool, approval, routing, and schema checks in `zone_b/agents/contract_checker.py`.
   - Schema remains `PASS` in fixture presentation data at `api/adapter.py:19-25` and `public/data.js`.

2. Routing contract is now deterministic backend behavior.
   - Fixture has VerifierAgent handing off to ReporterAgent with `verified_sources_count=0` at `zone_b/fixtures/sample_trace.json:38-47`.
   - Dashboard marks routing as `FAIL` in fixture data at `public/data.js:33` and `public/data.js:47`.
   - Sprint #13 added this as a backend lambda in `zone_b/agents/contract_checker.py` instead of treating it as presentation-only data.

3. Schema contract is deterministic backend behavior.
   - Fixture final output currently includes `summary`, `claims`, `citations`, `risks`, and `next_steps` at `zone_b/fixtures/sample_trace.json:56-62` and `zone_b/fixtures/sample_trace.json:80-86`.
   - Backend validates those required keys in `zone_b/agents/contract_checker.py:9-88`.
   - Sprint #14 keeps the current fixture passing for C-SCH.

4. Repair now emits one backend patch per violation.
   - Sprint #15 changed `run_repair` to return `patches[]` in violation input order and cardinality.
   - Legacy scalar repair fields still mirror the highest-severity patch for existing callers.
   - The dashboard adapter still creates visual patch rows by synthesis at `api/adapter.py:187-202`; passthrough of backend `report.patches[]` is assigned to #17.

5. Regression test generation was not deterministic enough for a gate. This has been stabilized in the follow-up fix.
   - Before the fix, if the generation call succeeded but returned a semantically bad test, the fallback was not used.
   - `_parse_status` turns sandbox stdout into `pass`, `fail`, or `error` at `zone_b/agents/regression_test.py:82-88`.
   - The fix reruns the deterministic fallback when a generated test returns `fail` or non-infrastructure `error`; see `zone_b/agents/regression_test.py:159-170`.
   - Explicit Daytona credential/API errors are still preserved as `error`; see `zone_b/agents/regression_test.py:91-101`.
   - Post-fix fixture and integration runs returned `Regression status : pass`.

6. API dependencies are split from editable-install dependencies.
   - `pyproject.toml` project dependencies include AG2, dotenv, Tavily, and Daytona, but not FastAPI.
   - `requirements.txt` includes FastAPI and Pydantic, but the current Python environment has not installed FastAPI.
   - Importing `api.index` fails because `api/index.py:19-22` imports FastAPI.

7. Handoff pre-flight references a missing document.
   - The project handoff requires reading `docs/PLAN_VS_REALITY.md`.
   - The file is missing locally; git history shows it was removed by commit `99a760f` during a revert of unauthorized doc pushes.

8. Local branch baseline is ahead of GitHub main.
   - `git log origin/main..HEAD --oneline` shows 19 commits ahead.
   - Any future PR from this branch to `main` will include baseline-sync work unless that is handled as a separate approved action.

## Recommended Gate Before #13

The regression gate blocker from this audit is stabilized. #13 may proceed after acknowledging the remaining toolchain gaps: `ruff` is unavailable, FastAPI is not installed in the current Python environment, and `docs/PLAN_VS_REALITY.md` is still missing.
