# Visual Regression Tests

Golden-screenshot tests that catch unintended UI drift on the Concord
dashboard. Driven by Playwright's `toHaveScreenshot` against the static
`public/` server on port 4173.

## Coverage

7 production dashboard screens × 2 viewports = 14 snapshots:

| Screen        | ID           | Desktop (1440x900) | Mobile (375x812) |
|---------------|--------------|--------------------|------------------|
| Overview      | `overview`   | yes                | yes              |
| Workflow DAG  | `topology`   | yes                | yes              |
| Agent Trace   | `trace`      | yes                | yes              |
| Violations    | `violations` | yes                | yes              |
| Repair Patch  | `repair`     | yes                | yes              |
| Regression    | `regression` | yes                | yes              |
| Final Report  | `report`     | yes                | yes              |

Sprint 16/17 screens (Forensic, Submit Run, Workflows) are stubbed as
`TODO_SCREENS` in `tests/e2e/visual/screens.spec.ts`. Uncomment and refresh
goldens when those PRs land in `production`.

## Run locally

```bash
npm install
npx playwright install chromium
npm run test:visual
```

The webserver is launched automatically by `playwright.config.ts`
(`python3 -m http.server 4173 -d public`).

## Update goldens

Run after any intentional UI change:

```bash
npm run test:visual:update
```

Review the diffs (`git diff tests/e2e/visual/screens.spec.ts-snapshots/`) and
commit only the snapshots that match the intended change.

## Diff threshold

We use Playwright's defaults: pixel-by-pixel comparison with
`maxDiffPixelRatio` unset (i.e., zero tolerance). Two reasons:

1. The dashboard is deterministic — fixture data, no animations, no live
   timestamps in the rendered surface area.
2. Tight thresholds catch subtle regressions (off-by-one paddings, color
   drift) that loose ones hide.

Genuine flake sources are masked instead of tolerated:

- `.status-line.muted` — UTC clock under the status cluster (live mode).

If a region is provably flaky for non-bug reasons (e.g., font hinting on a
new platform), prefer adding it to `dynamicMasks` over raising the
threshold. Last-resort: `toHaveScreenshot('foo.png', { maxDiffPixelRatio: 0.01 })`.

## Browser scope

Visual tests run only on the `chromium` project. Cross-engine pixel diffs
between Chromium and Firefox are noise, not signal — Firefox is exercised
by the functional specs (`fixture/`, `violation_path.spec.ts`).

## Platform-specific goldens

Playwright suffixes snapshots with the platform (e.g.
`overview-desktop-darwin.png`). Goldens generated on macOS will not match
Linux CI. The first CI run after this lands will need a one-time refresh
on the CI platform — commit those goldens as the canonical CI baseline.

## Where snapshots live

```
tests/e2e/visual/screens.spec.ts-snapshots/
  overview-desktop-darwin.png
  overview-mobile-darwin.png
  topology-desktop-darwin.png
  ...
```

This is Playwright's default — do not override `snapshotDir` unless the
whole project agrees on a different convention.

## CI integration

Add to the e2e job:

```yaml
- run: npm ci
- run: npx playwright install --with-deps chromium
- run: npm run test:visual
```

A failure uploads the actual/diff/expected triplet under
`playwright-report/` for review. Inspect via `npx playwright show-report`.
