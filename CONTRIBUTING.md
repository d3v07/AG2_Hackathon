# Contributing to Concord

Concord is an AG2-first contract-to-repair platform for multi-agent workflows. Contributions should make the core loop clearer or stronger:

```text
workflow contract -> trace/run -> deterministic violation -> AG2 primitive attribution
-> repair patch -> validation result -> persisted report/history -> export
```

Avoid broad rewrites, template-gallery expansion, or generic observability features unless they directly improve that loop.

## Before you start

1. Check the current GitHub issues and open pull requests.
2. Read the product source of truth in `docs/PLAN_VS_REALITY.md`.
3. For architecture context, read `docs/ARCHITECTURE.md`.
4. For demo behavior, read `docs/DEMO_SCRIPT.md`.
5. Keep changes vertical and small enough to review.

If a change affects runtime behavior, add or update tests in the same change.

## Local setup

Use Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
npm install
```

Run the API locally:

```bash
.venv/bin/python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
```

Run the deterministic fixture pipeline:

```bash
.venv/bin/python run_all.py --fixture
```

Fixture mode should remain available for local verification, but it should not be presented as the primary product path.

## Required checks

Run the smallest relevant checks while developing. Before opening a pull request, run:

```bash
.venv/bin/python -m pytest -x --tb=short
.venv/bin/python -m ruff check .
npm test -- --run
git diff --check
.venv/bin/python run_all.py --fixture
```

For frontend changes, also run the relevant Playwright suite:

```bash
npm run test:e2e -- tests/e2e/fixture/report_export.spec.ts --project=chromium
npm run test:a11y
```

For live-path changes, run the live smoke only when the required local credentials are available:

```bash
.venv/bin/python scripts/demo_e2e_smoke.py --runner local
pytest tests/e2e/live_smoke.py -m live_smoke -v --tb=short
```

Do not mark unavailable external validation as passed. Surface skipped, unavailable, credential failure, execution error, failed, and passed states honestly.

## Engineering rules

- Keep deterministic contract verdicts in code. Do not delegate verdicts to language-model output.
- Map violations to AG2 primitives explicitly and test the mapping.
- Preserve tenant isolation in every storage and API path.
- Keep API schemas stable unless the migration is intentional and tested.
- Keep repair output per violation; do not collapse multiple violations into one hidden primary patch.
- Keep validation results honest even when Daytona or other external services are unavailable.
- Do not commit secrets, local databases, exported reports with private data, or generated dependency directories.
- Prefer existing modules and patterns over new framework layers.
- Keep comments rare; use tests and clear names first.

## Frontend rules

- Build the usable product surface, not a marketing wrapper.
- Keep the UI focused on the repair loop: evidence, failed contract, failed AG2 primitive, patch, validation, and export/history.
- Do not hide audit surfaces just because a run has zero violations; clean runs are part of the product.
- Verify meaningful UI changes in a browser at desktop and mobile widths.
- Do not ship clipped text, inert controls, broken keyboard paths, or fake data states.

## Pull request checklist

Before requesting review, confirm:

- The branch is based on the latest `main`.
- The PR has a narrow purpose and clear acceptance criteria.
- Tests were added or updated for changed behavior.
- Required checks passed locally, or unavailable checks are documented with the reason.
- Public-facing copy says "Concord" unless historical context requires otherwise.
- No secrets or local-only artifacts are staged.
- Documentation was updated when behavior or workflows changed.

## Issue and branch style

- Use one branch per issue or tightly coupled pair of issues.
- Prefer branch names such as `feat/<short-scope>`, `fix/<short-scope>`, or `chore/<short-scope>`.
- Do not commit directly to `main`.
- Do not force-push shared branches.

