# Concord v1 PRD Launch Scorecard

Baseline date: 2026-05-31
Branch: `codex/issue-135-baseline-scorecard`
Issue: #135

Current north-star status is summarized in `docs/PLAN_VS_REALITY.md`. This scorecard remains the launch-criteria detail view.

## Verification

| Gate | Result | Notes |
| --- | --- | --- |
| `.venv/bin/python -m pytest -x --tb=short` | PASS | 519 passed, 1 skipped after #135-#137. |
| `npm test -- --run` | PASS | 1 frontend test file passed, 9 tests. |
| `.venv/bin/python -m ruff check .` | PASS | Project venv has `ruff`; bare `python3 -m ruff` fails because system Python has no `ruff`. |
| `git diff --check` | PASS | No whitespace errors. |
| `.venv/bin/python run_all.py --fixture` | PASS with honest credential state | Command exited 0 and produced the report. Invalid local Daytona credentials surface as `credential_failure`, not a fake pass. |
| API boot/probe | PASS | `uvicorn api.index:app --port 8765` booted; `/api/health` returned 200; `/?fixture=1` returned 200; authenticated `/api/runs/RUN-041` returned completed with 4 violations and 4 patches; disabled `/api/public/runs` returned 403. |

## Launch Criteria

PRD source: `concord_v1_artifacts/docs/CONCORD_PRD.md:320`.

| # | Criterion | Status | Evidence | Follow-up |
| --- | --- | --- | --- | --- |
| 1 | Create an API key. | PASS | Backend key creation and public status probe exist at `api/routes/api_keys.py:22`; the product UI API Access panel creates/reveals a session key, accepts an existing key, and avoids protected-route 401 noise before auth. | None |
| 2 | Register an AG2 workflow. | PASS | API supports workflow registration and `contracts_yaml` normalization at `api/routes/workflows.py:43`; landing UI imports JSON workflow specs or YAML contract DSL through `/api/workflows` or the opt-in same-origin relay at `public/app.jsx:2211`. | None |
| 3 | Submit a trace or run task. | PASS | Run submission route accepts task specs/raw traces at `api/routes/runs.py:61`; landing form posts live `task_spec` payloads at `public/app.jsx:2176`. | None |
| 4 | See live run status. | PASS | SSE token and event routes exist at `api/routes/runs.py:103` and `api/routes/runs.py:157`; frontend opens `EventSource` at `public/app.jsx:2803`. | None |
| 5 | View contract violations. | PASS | Five deterministic default contracts are registered in `zone_b/contracts/registry.py:13`; completed run probe returned 4 fixture violations. | None |
| 6 | See one repair per violation. | PASS | Native backend `patches[]` pass through in `api/adapter.py:459`; completed run probe returned 4 patches for 4 violations. | None |
| 7 | Run at least one regression test in Daytona. | PASS, credential-gated | Regression runner uses AG2 `DaytonaCodeExecutor` through `zone_b/sandbox/runner.py`; reports distinguish passed, failed, skipped, unavailable, credential failure, and execution error states instead of faking green validation. | #144 final demo should run with valid credentials |
| 8 | Export a report. | PASS | `EXPORT JSON` builds and downloads a complete report payload from `public/app.jsx:1863`. | None |
| 9 | Return later and see persisted history. | PASS | Sidebar fetches `/api/runs` at `public/app.jsx:2612`; API lists run ids at `api/routes/runs.py:36`. | None |

## Baseline Fixes

- Updated static dashboard tests to inspect both `public/index.html` and `public/app.jsx`, matching the current split frontend.
- Updated reporter shape test to expect `span_id`, which is now intentional violation evidence for span deep-linking.

## Local Progress After Baseline

#136 is implemented locally on `codex/issue-135-baseline-scorecard`: `EXPORT JSON` now downloads `concord-report-<run_id>.json`, attempts to copy the same JSON to clipboard, and includes verdicts, trace evidence, violations, patches, regression data, cost, run metadata, workflow metadata, and the final report block. Browser QA downloaded `concord-report-RUN-041.json` from `/?fixture=1` and verified 4 violations and 4 patches.

#137 is implemented locally on `codex/issue-135-baseline-scorecard`: public task submission no longer exposes a stub/live radio, the submitted task spec uses `mode: "live"`, and `TaskSpec` defaults to live when mode is omitted. Stub remains available only as an explicit internal/test mode. Browser QA verified the landing form has no mode radio, keeps the fixture CTA, and posts `mode: "live"` to the same-origin public relay when no browser tenant credentials exist.

#138 is implemented locally on `codex/issue-138-workflow-import`: the landing workflow selector now includes an import panel that accepts full JSON workflow specs or YAML contract DSL, posts to existing workflow validation through `/api/workflows` or an opt-in same-origin relay, shows validation errors inline, and selects the imported workflow without a page refresh.

#139 is implemented locally on `codex/issue-139-coherence-rebrand`: visible product chrome now uses Concord, and the completed-run violations table shows the evidence, AG2 primitive, patch, and regression status path in one row.

#140 is merged to `main`: Daytona validation states are explicit across regression, reporter, API adapter, dashboard, export JSON, fixture data, and CLI output.

#141 is merged to `main`: the landing page includes API Access for local first-key creation, existing-key bootstrap, one-time key reveal/copy, session-scoped storage, and auth-status preflight.
