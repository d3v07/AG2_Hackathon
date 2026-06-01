# Deployment

Concord has two deployable surfaces:

- FastAPI backend: run this on Render, Railway, or another container host.
- Static dashboard: Vercel can serve `public/index.html`, but it should point live-mode traffic at the hosted backend.

The hosted backend URL is a placeholder until the first credentialed deploy. After deploying, replace every occurrence of `https://<your-backend>.onrender.com` (or the Railway equivalent) in this doc with the actual URL, then re-run `./scripts/smoke_api.sh <URL>` to confirm.

## Local Stack

```bash
make dev
```

This builds the API image, starts FastAPI at `http://localhost:8000`, starts FalkorDB at `localhost:6379`, persists SQLite data in the `concord-data` volume, and persists graph data in the `falkordb-data` volume.

Verify it:

```bash
./scripts/smoke_api.sh http://localhost:8000
```

## Backend Container

The `Dockerfile` is multi-stage:

1. `builder` installs the project into `/install`.
2. `runtime` copies only installed packages, runtime source, and static dashboard assets.
3. The app runs as the non-root `concord` user.

Start command:

```bash
uvicorn api.index:app --host 0.0.0.0 --port ${PORT:-8000}
```

The Dockerfile reads provider `PORT` when present and defaults to `8000` for local compose.

## Environment

Required for API persistence:

```bash
CONCORD_DB_PATH=/app/data/concord.db
```

Optional graph persistence:

```bash
CONCORD_GRAPH_ENABLED=1
FALKORDB_HOST=<falkordb-host>
FALKORDB_PORT=6379
```

Required secrets for live pipeline runs:

```bash
OPENROUTER_API_KEY=<openrouter-key>   # required for Zone B LLM agents
TAVILY_API_KEY=<tavily-key>           # required for Zone A live web search
DAYTONA_API_KEY=<daytona-key>         # required for sandboxed regression tests
DAYTONA_API_URL=https://app.daytona.io/api
CONCORD_API_KEY=<tenant-api-key>      # required for authenticated API calls
```

These four keys — `OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `DAYTONA_API_KEY`, and `CONCORD_API_KEY` — are the minimum set needed to run a fully live end-to-end pipeline. `CONCORD_API_KEY` is minted at first startup via `POST /api/api-keys` (see ONBOARDING.md step 2).

Daytona credentials are not required for the API to start; missing credentials produce an explicit regression-test infrastructure error instead of a fake pass.

## Render

1. Create a new Web Service from this repository.
2. Use the Docker runtime.
3. Set the branch to `production`.
4. Add a persistent disk mounted at `/app/data`.
5. Add the environment variables above.
6. Deploy and run:

   ```bash
   ./scripts/smoke_api.sh https://<render-service>.onrender.com
   ```

## Railway

1. Create a new project from this repository.
2. Select Dockerfile-based deployment.
3. Add a persistent volume mounted at `/app/data`.
4. Add a FalkorDB/Redis-compatible service or set `CONCORD_GRAPH_ENABLED=0`.
5. Add the environment variables above.
6. Deploy and run:

   ```bash
   ./scripts/smoke_api.sh https://<railway-service>.up.railway.app
   ```

## Vercel Frontend Wiring

The dashboard defaults to fixture mode. Do not publish a tenant API key in static HTML, checked-in wrappers, or public environment variables. A tenant API key can create more keys and read tenant usage, so it belongs on a server.

For hosted live submissions served from the same origin, enable the built-in public run relay with `CONCORD_PUBLIC_RUNS_ENABLED=1` and `CONCORD_PUBLIC_TENANT_ID=<tenant>`. It accepts task submissions only and creates runs under the configured tenant without exposing a browser API key. Keep raw trace submission, tenant usage, workflow writes, and API key management behind authenticated API routes.

If the hosted product should also allow landing-page workflow imports without browser tenant keys, enable `CONCORD_PUBLIC_WORKFLOWS_ENABLED=1`. Leave it disabled for private/operator-only environments.

For private local operator testing only, you can set the run ID and tenant ID in a browser session before switching to LIVE mode:

```html
<script>
window.CONCORD_RUN_ID = "RUN-...";
window.CONCORD_TENANT_ID = "tenant-a";
</script>
```

Browser EventSource should use a short-lived stream token minted by the authenticated backend path, not a long-lived tenant key embedded in the page.

## CI

`.github/workflows/ci.yml` runs:

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
pytest -x --tb=short
```

The workflow runs on pushes and pull requests targeting `main` or `production`.

## Live Smoke Test (post-PR-#94 merge)

Once PR #94 lands on `production`, a `workflow_dispatch`-triggered workflow will be available at `.github/workflows/live-smoke.yml`. To trigger it manually:

1. Go to the repository Actions tab on GitHub.
2. Select the `Live Smoke` workflow.
3. Click `Run workflow`, choose the `production` branch, and confirm.
4. The workflow runs `tests/e2e/live_smoke.py` against the hosted backend URL.
5. Expected cost per run: placeholder — update after the first live-smoke run completes.

The secrets `OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `DAYTONA_API_KEY`, and `CONCORD_API_KEY` must be configured in the repository's Actions secrets before the first run.

## Branch Protection

Branch protection cannot be configured from this local environment. Manual setting:

1. Open GitHub repository settings.
2. Go to Branches.
3. Add a rule for `main`.
4. Enable `Require a pull request before merging`.
5. Enable `Require status checks to pass before merging`.
6. Select the `CI / test` check after the first workflow run appears.
7. Enable `Require branches to be up to date before merging`.

Repeat for `production` if you want the same protection before the main promotion PR.
