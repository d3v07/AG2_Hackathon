# Deployment

Concord has two deployable surfaces:

- FastAPI backend: run this on Render, Railway, or another container host.
- Static dashboard: Vercel can serve `public/index.html`, but it should point live-mode traffic at the hosted backend.

No hosted deploy was executed in this sprint because provider credentials are not available in the local environment. The code, scripts, and configuration below are ready for a credentialed operator.

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

Optional live integrations:

```bash
OPENROUTER_API_KEY=<provider-key>
TAVILY_API_KEY=<tavily-key>
DAYTONA_API_KEY=<daytona-key>
DAYTONA_API_URL=<daytona-api-url>
```

Daytona credentials are not required for the API to start; missing credentials produce an explicit regression-test infrastructure error instead of a fake pass.

## Render

1. Create a new Web Service from this repository.
2. Use the Docker runtime.
3. Set the branch to `main`.
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

For hosted live mode, add a small authenticated backend-for-frontend that keeps the tenant key server-side, calls the Concord API from the server, and returns only the run payload plus a short-lived event stream token to the browser.

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
