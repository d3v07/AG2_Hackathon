# Onboarding

This path takes a first-time user from a clean local stack to a completed contract report.

## 1. Start Concord

```bash
make dev
```

In another terminal:

```bash
./scripts/smoke_api.sh http://localhost:8000
```

Expected output:

```text
health check passed: http://localhost:8000/api/health status=ok
```

The dashboard is available at `http://localhost:8000`.

## 2. Create an API Key

Local development allows the first key to be created from localhost.

Endpoint: `POST /api/api-keys`

```bash
export CONCORD_API=http://localhost:8000

export CONCORD_API_KEY="$(
  curl -fsS -X POST "$CONCORD_API/api/api-keys" \
    -H 'Content-Type: application/json' \
    -d '{"tenant_id":"tenant-a","name":"tenant-a primary"}' \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["api_key"])'
)"
```

Use the key for every protected API call:

```bash
AUTH_HEADER="Authorization: Bearer $CONCORD_API_KEY"
```

## 3. Register a Workflow

Endpoint: `POST /api/workflows`

```bash
export WORKFLOW_ID="$(
  curl -fsS -X POST "$CONCORD_API/api/workflows" \
    -H "$AUTH_HEADER" \
    -H 'Content-Type: application/json' \
    -d '{
      "name": "LiteratureReviewAssistant",
      "owner": "tenant-a",
      "declared_topology": {
        "entry": "ResearcherAgent",
        "edges": [
          {"from": "ResearcherAgent", "to": "VerifierAgent"},
          {"from": "VerifierAgent", "to": "ReporterAgent", "expected_tool_event": true},
          {"from": "ReporterAgent", "to": "ActionAgent"}
        ]
      },
      "agents": [
        {"name": "ResearcherAgent"},
        {"name": "VerifierAgent"},
        {"name": "ReporterAgent"},
        {"name": "ActionAgent"}
      ],
      "tools": [{"name": "tavily_search"}],
      "contracts": [
        {"id": "C-EVD", "type": "evidence", "rule": "verified_sources_count must be > 0"},
        {"id": "C-TOL", "type": "tool", "rule": "VerifierAgent must record a tool_call_id"},
        {"id": "C-RTE", "type": "routing", "rule": "ReporterAgent requires a successful VerifierAgent tool event"},
        {"id": "C-APR", "type": "approval", "rule": "ActionAgent requires approval_status == approved"}
      ]
    }' \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["workflow_id"])'
)"
```

Confirm registration:

```bash
curl -fsS "$CONCORD_API/api/workflows/$WORKFLOW_ID" -H "$AUTH_HEADER"
```

## 4. Submit a Trace

Endpoint: `POST /api/runs`

```bash
export RUN_ID="$(
  python3 - <<'PY' | curl -fsS -X POST "$CONCORD_API/api/runs" \
    -H "$AUTH_HEADER" \
    -H 'Content-Type: application/json' \
    -d @- \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["run_id"])'
import json
import os
from pathlib import Path

trace = json.loads(Path("zone_b/fixtures/sample_trace.json").read_text())
print(json.dumps({"workflow_id": os.environ["WORKFLOW_ID"], "raw_trace": trace}))
PY
)"
```

Poll status:

```bash
curl -fsS "$CONCORD_API/api/runs/$RUN_ID/status" -H "$AUTH_HEADER"
```

Fetch the report:

Endpoint: `GET /api/runs/{run_id}`

```bash
curl -fsS "$CONCORD_API/api/runs/$RUN_ID" -H "$AUTH_HEADER"
```

Open the dashboard:

```text
http://localhost:8000/?run=<RUN_ID>
```

Hosted static pages must not embed tenant API keys. Keep the dashboard in fixture mode, or put a small authenticated backend in front of LIVE mode that keeps the tenant key server-side and returns only a run payload plus short-lived stream token.

## 5. Review Usage

Endpoint: `GET /api/tenant/usage`

```bash
curl -fsS "$CONCORD_API/api/tenant/usage" -H "$AUTH_HEADER"
```

The response includes:

```json
{
  "tenant_id": "tenant-a",
  "period": "all",
  "run_count": 1,
  "daytona_seconds": 0.0,
  "llm_tokens": 0,
  "llm_cost_usd": 0.0,
  "daytona_cost_usd": 0.0,
  "total_cost_usd": 0.0
}
```

## Troubleshooting

- `401 missing API key`: send `Authorization: Bearer <key>`.
- `404 workflow not found`: the workflow belongs to another tenant or the ID is wrong.
- `Regression status: error`: check `DAYTONA_API_KEY` and `DAYTONA_API_URL`.
- Graph data missing: check `CONCORD_GRAPH_ENABLED`, `FALKORDB_HOST`, and `FALKORDB_PORT`.
