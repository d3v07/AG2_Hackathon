# Concord Final Demo Script

This is the current Concord v1 demo path. It replaces the old stage cue cards and avoids the retired seven-tab story.

## What This Demo Proves

| Step | Product proof | Current surface |
|---:|---|---|
| 1 | Create or load tenant API access | Landing `API Access` panel and `POST /api/api-keys` |
| 2 | Register a workflow contract | Landing import panel and `POST /api/workflows` with JSON or `contracts_yaml` |
| 3 | Submit a run | Landing run form for `task_spec`, or API `POST /api/runs` with `raw_trace` |
| 4 | Catch deterministic violations | Zone B contract checker finds evidence, tool, routing, and approval failures |
| 5 | Attribute and repair | Report links each violation to an AG2 primitive patch |
| 6 | Validate repair state | Regression block reports `passed`, `failed`, `credential_failure`, `execution_error`, `unavailable`, or `skipped` |
| 7 | Export report | `EXPORT JSON` emits the completed report payload |
| 8 | Revisit history | Sidebar history and `GET /api/runs/{run_id}` reload the completed run |

## Fast Automated Smoke

Run this before any recorded demo or release handoff:

```bash
.venv/bin/python scripts/demo_e2e_smoke.py
npm run test:e2e -- tests/e2e/fixture/report_export.spec.ts --project=chromium
```

The smoke creates a temporary SQLite database, creates a local API key, imports the literature-review contract YAML, submits `zone_b/fixtures/sample_trace.json`, verifies four violations, verifies four repair patches, verifies four regression assertions, checks validation state honesty, and revisits the run through history.

The Playwright check opens the actual fixture report screen, clicks `EXPORT JSON`, downloads the report, and verifies the exported JSON contains run metadata, verdicts, violations, patches, regression data, and cost.

Expected ending:

```text
PASS demo_e2e_smoke
run_id=RUN-... workflow_id=WF-... violations=4 patches=4 assertions=4 validation_state=...
```

For a fast deterministic local check that does not touch the sandbox provider:

```bash
CONCORD_DEMO_REGRESSION_RUNNER=local .venv/bin/python scripts/demo_e2e_smoke.py
```

`CONCORD_DEMO_REGRESSION_RUNNER=product` is the default. It uses the product validation path and accepts honest unavailable or credential-failure states when sandbox credentials are absent or invalid.

## Browser Demo Setup

Start the local API and static app:

```bash
CONCORD_DB_PATH=data/demo.db \
CONCORD_PUBLIC_WORKFLOWS_ENABLED=1 \
CONCORD_PUBLIC_RUNS_ENABLED=1 \
.venv/bin/python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Browser Walkthrough

1. **Create API access.** Open `API Access`, create a `local` browser session key, and confirm the status reads `READY`.
2. **Import workflow contract.** Open `Import workflow contract`, enter `LiteratureReviewAssistant`, paste the contents of `zone_b/contracts/examples/literature_review.yaml`, and import it.
3. **Submit a live task when runtime credentials are present.** Pick the imported workflow, enter a task and research question, and click `Run task`.
4. **If runtime credentials are not present, use the completed fixture for the visual walkthrough.** Click `View demo fixture run`. The backend smoke above is the proof of the actual API loop.
5. **Walk the completed report.** Show the contract count, violation list, topology, repair patches, regression panel, validation state, and final narrative.
6. **Export.** Click `EXPORT JSON`; confirm the payload contains `run`, `violations`, `patches`, `test`, `report`, and `cost`.
7. **Revisit.** Use the sidebar recent-run list to reopen the completed run.

## Talk Track

**"Concord is a contract-to-repair system for AG2 workflows. The workflow declares what must be true, Concord reads the trace, finds deterministic contract violations, maps each one to the responsible AG2 primitive, proposes a repair patch, validates the patch state, and stores the report so the operator can export or revisit it."**

**"The important part is separation. The workflow under test can be wrong in its narrative. Concord does not trust the narrative; it reads the trace and applies code-level contracts."**

**"A clean run is allowed. Concord is not supposed to force failure. When a workflow does fail, the report links evidence, failed agent, failed step, repair patch, regression result, validation state, and exportable metadata in one place."**

## Honest Validation Language

Use this wording when the validation block is not green:

| State | Say this |
|---|---|
| `passed` | "The repair regression passed." |
| `failed` | "The repair was tested and did not satisfy the regression." |
| `credential_failure` | "The validation runner was reached, but credentials were missing or invalid. Concord is not pretending this passed." |
| `execution_error` | "The validation runner errored during execution. The report preserves that state." |
| `unavailable` | "Validation did not produce a runnable sandbox result in this environment." |
| `skipped` | "There were no violations to validate." |

## API Flow For Q&A

```bash
# Health
curl -s http://127.0.0.1:8000/api/health

# Create a local key
curl -s -X POST http://127.0.0.1:8000/api/api-keys \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"local","name":"demo"}'

# Register a workflow with normalized YAML contracts
curl -s -X POST http://127.0.0.1:8000/api/workflows \
  -H "Authorization: Bearer $CONCORD_API_KEY" \
  -H 'Content-Type: application/json' \
  -d @workflow.json

# Submit a run
curl -s -X POST http://127.0.0.1:8000/api/runs \
  -H "Authorization: Bearer $CONCORD_API_KEY" \
  -H 'Content-Type: application/json' \
  -d @run.json

# Fetch report and history
curl -s http://127.0.0.1:8000/api/runs/$RUN_ID -H "Authorization: Bearer $CONCORD_API_KEY"
curl -s http://127.0.0.1:8000/api/runs -H "Authorization: Bearer $CONCORD_API_KEY"
```

## Files To Open If Asked

| Question | File |
|---|---|
| Workflow contracts | `zone_b/contracts/examples/literature_review.yaml` |
| Deterministic checks | `zone_b/contracts/registry.py` and `zone_b/agents/contract_checker.py` |
| Repair patches | `zone_b/agents/repair.py` |
| Regression validation | `zone_b/agents/regression_test.py` and `zone_b/sandbox/runner.py` |
| API routes | `api/routes/workflows.py`, `api/routes/runs.py`, `api/routes/api_keys.py` |
| Dashboard export | `public/app.jsx` `buildReportExportPayload()` |
| Automated demo proof | `scripts/demo_e2e_smoke.py` |

## Final Line

**"Concord turns AG2 traces into deterministic verdicts, targeted repair patches, honest validation states, and a report the operator can export or revisit."**
