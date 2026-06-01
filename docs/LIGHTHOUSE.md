# Lighthouse CI

Automated performance, accessibility, best-practices, and SEO budgets for the
Concord dashboard (`public/index.html`). Configuration lives in
[`lighthouserc.json`](../lighthouserc.json) at the repo root.

## Run locally

Prerequisites: Node 20+ and Google Chrome (or Chromium) installed.

```sh
npm install
npm run lighthouse           # full collect + assert + upload pipeline
npm run lighthouse:collect   # collect run only, no assertion
npm run lighthouse:assert    # assert against an existing collect
```

`lhci autorun` boots a static server pointed at `public/`, runs Lighthouse one
time per URL, asserts the category scores against the configured budgets, and
uploads the report to temporary public storage. The local artifacts land in
`.lighthouseci/` (gitignored — `lhr-*.html` is the human-readable report).

A non-zero exit on assertion failure is expected and surfaces in CI logs. The
GitHub workflow (`.github/workflows/lighthouse.yml`) sets
`continue-on-error: true` so a single missed budget does not block PRs while we
stabilize the baseline.

## Budgets

| Category        | Min score | Rationale |
| --------------- | --------- | --------- |
| performance     | 0.85      | Single-page React-via-CDN dashboard with no build step. 0.85 is achievable on desktop preset and forces us to keep CDN bundle weight in check. |
| accessibility   | 0.95      | Operator-facing tooling. Target near-perfect because keyboard nav, contrast, and labelling are non-negotiable for a control surface. |
| best-practices  | 0.90      | Catches mixed-content, deprecated APIs, console errors, vulnerable libraries. Cheap to keep above 0.90 on a static page. |
| seo             | 0.80      | Internal tool, not crawled — but Lighthouse's SEO checks (meta description, viewport, link text) double as quality hygiene. |

## Baseline (desktop preset, `public/index.html`)

Captured on 2026-05-08 against the current `production` build.

| Category        | Score | Budget | Status |
| --------------- | ----- | ------ | ------ |
| performance     | 0.85  | 0.85   | meets  |
| accessibility   | 0.94  | 0.95   | **below — follow-up** |
| best-practices  | 0.96  | 0.90   | meets  |
| seo             | 0.90  | 0.80   | meets  |

### Known follow-up

Accessibility is one point shy of the 0.95 budget. Per project policy the
budget is the goal, not the current state — so the 0.95 floor stays. Triage
the audit categories surfaced in the latest `.lighthouseci/lhr-*.html` report
(typically colour-contrast or missing form labels for a dashboard of this
shape) and file a follow-up issue rather than relaxing the threshold.

## Updating budgets

Budgets are intentionally tight. Only relax them when a screen has a
structural reason it cannot meet the floor (e.g. a heavy data-grid view that
genuinely needs `performance < 0.85`). To change a budget:

1. Capture before/after Lighthouse runs and link the report URLs in the PR.
2. Edit the relevant `categories:*` entry in `lighthouserc.json`.
3. Document the per-screen rationale in this file (add a row under
   "Per-screen overrides" once the dashboard splits into routed views).
4. Have the change reviewed — budgets are a contract, not a knob.

To add a new screen URL once the dashboard supports deep-linking, append to
`ci.collect.url` and, if needed, override the assertion under
`ci.assert.assertMatrix` keyed on the URL pattern.
