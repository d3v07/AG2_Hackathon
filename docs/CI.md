# CI Test Pyramid

## Job map

| Job | Trigger | Runner | Timeout |
|-----|---------|--------|---------|
| backend-tests | every push / PR | ubuntu-latest | 15 min |
| frontend-vitest | every push / PR (when package.json present) | ubuntu-latest | 10 min |
| frontend-e2e | every push / PR (when package.json present) | ubuntu-latest | 20 min |
| frontend-a11y | every push / PR (when package.json present) | ubuntu-latest | 15 min |
| live-smoke | workflow_dispatch only | ubuntu-latest | 30 min |
| lighthouse | push to main/production + schedule | ubuntu-latest | 20 min |

All jobs in ci.yml run in parallel. live-smoke and Lighthouse are separate workflows.

## Which job runs when

    Every push / PR:
      backend-tests     always
      frontend-vitest   only if package.json exists in the tree
      frontend-e2e      only if package.json exists in the tree
      frontend-a11y     only if package.json exists in the tree

    Manual dispatch only:
      live-smoke        .github/workflows/live-smoke.yml

    Scheduled / push to main|production:
      lighthouse        .github/workflows/lighthouse.yml

The frontend jobs use "if: hashFiles(package.json) != empty". They silently skip (not fail) on PRs that predate the frontend PRs (#106, #118, #120). Once those PRs land and package.json is on production, the guard is always true.

## Running each layer locally

### Backend pytest (stub mode, no API keys needed)

    pip install -e . -r requirements-dev.txt
    pytest -x --tb=short

### Frontend Vitest unit tests

    npm ci
    npm test

### Playwright E2E (fixture mode, no live server needed)

    npm ci
    npx playwright install chromium firefox --with-deps
    npm run test:e2e

### axe-core a11y scan

    npm ci
    npx playwright install chromium --with-deps
    npm run test:a11y

### Live smoke (needs all API keys)

    pytest -m live_smoke

### Lighthouse (needs a running frontend)

    npm run lighthouse

## Skipping a slow job temporarily

Option 1 - commit message (push events only):

    git commit -m "chore: tweak README [skip ci]"

GitHub Actions respects [skip ci] in the commit message for push events. PRs cannot be skipped this way.

Option 2 - disable the workflow via gh CLI:

    gh workflow disable "CI"
    # ... land your PR ...
    gh workflow enable "CI"

Option 3 - path filters: Add paths: under on.push / on.pull_request for that specific workflow. Not currently set - every push triggers all jobs.

## Required secrets

### Main CI (ci.yml)

None. Every job runs in stub/fixture mode. No API keys needed.

### Lighthouse (lighthouse.yml)

None required for default LHCI configuration (runs against a local static build).

### Live smoke (live-smoke.yml)

All four keys must be set as GitHub Actions secrets on the repository:

| Secret | Used by |
|--------|---------|
| OPENROUTER_API_KEY | Zone A + Zone B LLM calls (Gemini via OpenRouter) |
| TAVILY_API_KEY | Zone A ResearcherAgent (web search) |
| DAYTONA_API_KEY | Zone B RegressionTest (sandbox execution) |
| DAYTONA_API_URL | Zone B RegressionTest (sandbox API endpoint) |
| CONCORD_API_KEY | Optional - tenant-scoped API auth smoke tests |

Set them at: https://github.com/d3v07/AG2_Hackathon/settings/secrets/actions
