# Concord v1 PRD Launch Scorecard

Baseline date: 2026-05-31
Branch: `codex/issue-135-baseline-scorecard`
Issue: #135

## Verification

| Gate | Result | Notes |
| --- | --- | --- |
| `.venv/bin/python -m pytest -x --tb=short` | PASS | 519 passed, 1 skipped after #135-#137. |
| `npm test -- --run` | PASS | 1 frontend test file passed, 9 tests. |
| `.venv/bin/python -m ruff check .` | PASS | Project venv has `ruff`; bare `python3 -m ruff` fails because system Python has no `ruff`. |
| `git diff --check` | PASS | No whitespace errors. |
| `.venv/bin/python run_all.py --fixture` | PASS with validation gap | Command exited 0 and produced the report. Daytona sandbox creation failed with invalid credentials, so regression status was `error` / `no-sandbox`. Tracked by #140. |
| API boot/probe | PASS | `uvicorn api.index:app --port 8765` booted; `/api/health` returned 200; `/?fixture=1` returned 200; authenticated `/api/runs/RUN-041` returned completed with 4 violations and 4 patches; disabled `/api/public/runs` returned 403. |

## Launch Criteria

PRD source: `concord_v1_artifacts/docs/CONCORD_PRD.md:320`.

| # | Criterion | Status | Evidence | Follow-up |
| --- | --- | --- | --- | --- |
| 1 | Create an API key. | PARTIAL | Backend route exists at `api/routes/api_keys.py:13`; live public submissions can use the server-side relay at `api/routes/public_runs.py:21`, but in-product key creation is still missing. | #141 |
| 2 | Register an AG2 workflow. | PARTIAL | API supports workflow registration and `contracts_yaml` normalization at `api/routes/workflows.py:42`; landing UI only exposes a picker and tells users to `POST /api/workflows` first at `public/app.jsx:1695`. | #138 |
| 3 | Submit a trace or run task. | PASS | Run submission route accepts task specs/raw traces at `api/routes/runs.py:63`; landing form posts live `task_spec` payloads at `public/app.jsx:1791`. | None |
| 4 | See live run status. | PASS | SSE token and event routes exist at `api/routes/runs.py:105` and `api/routes/runs.py:148`; frontend opens `EventSource` at `public/app.jsx:1988`. | None |
| 5 | View contract violations. | PASS | Five deterministic default contracts are registered in `zone_b/contracts/registry.py:13`; completed run probe returned 4 fixture violations. | None |
| 6 | See one repair per violation. | PASS | Native backend `patches[]` pass through in `api/adapter.py:459`; completed run probe returned 4 patches for 4 violations. | None |
| 7 | Run at least one regression test in Daytona. | PARTIAL | Regression runner exists in `zone_b/agents/regression_test.py`; current local fixture run hit Daytona invalid credentials and surfaced `error` / `no-sandbox`. | #140 |
| 8 | Export a report. | PASS | `EXPORT JSON` builds a complete report payload at `public/app.jsx:79`, downloads it through `public/app.jsx:155`, and is wired from `public/app.jsx:1688`. | #136 |
| 9 | Return later and see persisted history. | PASS | Sidebar fetches `/api/runs` at `public/app.jsx:1798`; API lists run ids at `api/routes/runs.py:35`. | None |

## Baseline Fixes

- Updated static dashboard tests to inspect both `public/index.html` and `public/app.jsx`, matching the current split frontend.
- Updated reporter shape test to expect `span_id`, which is now intentional violation evidence for span deep-linking.

## Local Progress After Baseline

#136 is implemented locally on `codex/issue-135-baseline-scorecard`: `EXPORT JSON` now downloads `concord-report-<run_id>.json`, attempts to copy the same JSON to clipboard, and includes verdicts, trace evidence, violations, patches, regression data, cost, run metadata, workflow metadata, and the final report block. Browser QA downloaded `concord-report-RUN-041.json` from `/?fixture=1` and verified 4 violations and 4 patches.

#137 is implemented locally on `codex/issue-135-baseline-scorecard`: public task submission no longer exposes a stub/live radio, the submitted task spec uses `mode: "live"`, and `TaskSpec` defaults to live when mode is omitted. Stub remains available only as an explicit internal/test mode. Browser QA verified the landing form has no mode radio, keeps the fixture CTA, and posts `mode: "live"` to the same-origin public relay when no browser tenant credentials exist.
