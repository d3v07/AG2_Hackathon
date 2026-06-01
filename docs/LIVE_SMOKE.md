# Live E2E Smoke

End-to-end smoke test that exercises the full Concord stack against a
real backend: `task_spec` submission → AG2 swarm execution → Zone B contract
checking → Daytona regression → forensic `CONCORD_DATA` → operator approval.

This test costs real LLM, Tavily, and Daytona credits. It is opt-in.

## When it runs

- **Locally**: `pytest tests/e2e/live_smoke.py -m live_smoke -v` with the
  required env vars set.
- **CI**: only via `workflow_dispatch` on `.github/workflows/live-smoke.yml`.
  Never on PRs, never on schedule.

## Required environment

| Variable | Purpose |
|---|---|
| `CONCORD_API_BASE` | Backend URL (default `http://localhost:8000`) |
| `CONCORD_API_KEY` | API key for tenant-scoped routes (optional for `local` tenant) |
| `OPENROUTER_API_KEY` | LLM credentials — gate variable; absence skips the test |
| `TAVILY_API_KEY` | Search backend for Zone A's ResearcherAgent |
| `DAYTONA_API_KEY` | Sandboxed regression executor |

The test skips with a clear message when `OPENROUTER_API_KEY` is unset, so a
forgotten credential never produces a confusing failure.

## Run locally

```bash
export CONCORD_API_BASE=http://localhost:8000
export OPENROUTER_API_KEY=...
export TAVILY_API_KEY=...
export DAYTONA_API_KEY=...
pytest tests/e2e/live_smoke.py -m live_smoke -v --tb=short
```

## Run on CI (manual dispatch)

1. GitHub → Actions → "Live E2E Smoke" → "Run workflow"
2. Optionally override `concord_api_base`
3. Watch the logs; pytest output is uploaded as an artifact

## Expected runtime and cost

| Phase | Wall-clock | Credit category |
|---|---|---|
| Workflow registration + run submit | <1s | API only |
| AG2 swarm (Researcher → … → Action) | 30–90s | OpenRouter + Tavily |
| Zone B contract check | <2s | none |
| Repair iteration (when violations) | 20–60s | OpenRouter |
| Daytona regression | 30–60s | Daytona sandbox seconds |
| Approval | <1s | API only |
| **Total** | ~2–3 min | ~\$0.10–\$0.50 per run (refine after first measurement) |

## What it asserts

1. `POST /api/runs` returns 202
2. Status reaches `completed` (or `failed` — explicit assertion)
3. `CONCORD_DATA.spans` is a non-empty list (Sprint 15 #74 contract)
4. Every violation carries `span_id` (Sprint 15 #75 contract)
5. Every patch has a corresponding regression result
6. Approval workflow completes; status updates to `APPROVED`

## When it fails

- **Skip**: missing `OPENROUTER_API_KEY` → `pytest` reports SKIPPED with a
  reason. Not a failure.
- **Timeout** (180s): the swarm or regression hung. Inspect API logs and
  Daytona dashboard.
- **Assertion failure**: a contract from Sprint 15 broke. Check the offending
  PR for regressions.

## After Sprint 18 polish lands

This test is a stable contract for the deployed dashboard. Bumping the
asserted span shape (16 fields) or kind enum (10 kinds) is a breaking change
— update both this test and the corresponding documentation in `docs/ARCHITECTURE.md`.
