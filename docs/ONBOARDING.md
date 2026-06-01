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

### Run modes

| Mode | Command | What runs | Credentials needed |
|------|---------|-----------|-------------------|
| live | `python run_all.py` | Zone A + Zone B end-to-end | `OPENROUTER_API_KEY`, `TAVILY_API_KEY` |
| fixture demo | `python run_all.py --fixture` | Zone B pipeline on pre-baked trace | none |
| swarm live | `python run_all.py --swarm` | Zone A swarm + Zone B GroupChat | `OPENROUTER_API_KEY`, `TAVILY_API_KEY` |
| swarm fixture | `python run_all.py --swarm --fixture` | Zone B GroupChat on pre-baked trace | `OPENROUTER_API_KEY` |

**fixture demo** uses `zone_b/fixtures/sample_trace.json` — 5 pre-baked agent turns with 4 violations, always produces the same deterministic output. Use this to explore the pipeline without spending LLM credits or standing up Tavily.

**live mode** calls Tavily for real web search results, then runs all seven Zone B agents through Gemini 2.5 Flash. Set `DAYTONA_API_KEY` to enable the sandboxed regression test stage; without it the stage returns `test_status=error` rather than silently passing.

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

## 4. Submit a Run

Endpoint: `POST /api/runs`

The body accepts exactly one of `raw_trace` or `task_spec`:

- `raw_trace`: a full AG2-shaped trace dict. Runs Zone B only. Fully wired today.
- `task_spec`: task metadata that drives Zone A end-to-end. Schema is accepted but runtime execution requires Zone A credentials; currently returns HTTP 400 until Zone A runtime wiring lands.

### Submit via raw_trace (fully supported)

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

### Submit via task_spec

Submit a task specification directly:

```bash
curl -X POST "$CONCORD_API/api/runs" \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -d '{
    "workflow_id": "'"$WORKFLOW_ID"'",
    "task_spec": {
      "task": "Create a literature review memo on whether multi-agent systems improve reliability in research workflows.",
      "research_question": "Do multi-agent systems improve reliability in research workflows?"
    }
  }'
```

Omitting `mode` uses live execution. `mode` is still accepted for internal tests:

- `live`: runs Zone A end-to-end with Tavily search and Gemini LLM — requires `TAVILY_API_KEY` and `OPENROUTER_API_KEY`.
- `stub`: deterministic internal test run on the clean stub trace.

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

Hosted static pages must not embed tenant API keys. For same-origin hosted live submissions, enable the server-side public run relay with `CONCORD_PUBLIC_RUNS_ENABLED=1` and `CONCORD_PUBLIC_TENANT_ID=<tenant>`. The relay accepts task submissions only, keeps tenant credentials server-side, and leaves raw trace submission behind authenticated API routes.

## 5. Reading the Forensic Span Tree (available once PRs #110-#113 land)

The Forensic screen displays the full execution trace as a tree of spans. Each span represents one unit of work in the pipeline.

### Span kinds

| Kind | What it represents |
|------|-------------------|
| `workflow` | Top-level workflow execution envelope |
| `agent` | A single agent's reasoning turn |
| `tool` | A tool call (Tavily search, Daytona exec, etc.) |
| `handoff` | Agent-to-agent transfer |
| `guardrail` | Output guardrail check (e.g., RegexGuardrail) |
| `human_gate` | Human approval gate |
| `action` | Side-effect agent action |
| `contract_check` | Zone B contract enforcement check |
| `repair` | Zone B repair patch generation |
| `regression` | Zone B Daytona sandbox regression test |

### Reading the inspector

Click any span in the tree to open the inspector panel. Sections:

- **Identity**: span ID, parent span ID, trace ID, name, kind, agent, tool.
- **Timing**: start time, end time, duration in milliseconds.
- **Error**: error message if the span failed, otherwise empty.
- **Input**: the input payload the span received.
- **Output**: the output the span produced.
- **Attributes**: all additional span attributes as key-value pairs.
- **Contract violations**: any contract IDs that this span is linked to, with severity and a deep-link to the Violations screen.
- **Repair**: the repair patch associated with this span's violation, if one exists.
- **Regression**: the regression test result for this span's repair patch.

Violation badges on a span indicate the contract was checked against that span's output and failed. Click the badge to jump directly to the violation detail.

## 6. Review Usage

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
- `400 task_spec submission requires Zone A runtime wiring`: use `raw_trace` instead until Zone A wiring lands.
- `404 workflow not found`: the workflow belongs to another tenant or the ID is wrong.
- `Regression status: error`: check `DAYTONA_API_KEY` and `DAYTONA_API_URL`.
- Graph data missing: check `CONCORD_GRAPH_ENABLED`, `FALKORDB_HOST`, and `FALKORDB_PORT`.
- Zone A errors with `--fixture` flag absent: check `OPENROUTER_API_KEY` is set; use `--fixture` to skip Zone A.
