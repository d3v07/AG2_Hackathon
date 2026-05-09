# Legacy frontend tests (abandoned dev module)

These 12 test files cover components from the **dev `public/app.jsx` module**
that drifted from the production-rendered inline JSX during Sprints 16-17.

When Phase 1 of the frontend rebuild reconciled `public/app.jsx` with what
production was actually rendering, the dev components these tests target
(`SubmitRun`, `Forensic`, `SpanTree`, `SpanInspector`, `TimelineWaterfall`,
`RunProgress`, `ApprovalPanel`, `LoadingState`, `EmptyState`, `ErrorState`,
`WorkflowsScreen`, `ViewSpanLink`, etc.) ceased to exist on the canonical
module.

## Why they're here, not deleted

These tests document the **target API contract** for components that
Phases 3-7 of the frontend rebuild will reintroduce as part of the new
user-facing product flow:

- Phase 3 LiveRun → reintroduces `useRunEventStream` (covered by
  `run_progress.test.jsx`)
- Phase 4 RunResult → reintroduces ApprovalPanel-equivalent
  (`approval_panel.test.jsx`)
- Phase 5 Zone B reactive → uses LoadingState/EmptyState/ErrorState
  (`states.test.jsx`)
- Phase 6 Forensic drill-down → repurposes SpanTree/TimelineWaterfall/
  SpanInspector (the three corresponding test files)
- Phase 7 polish → a11y + deep-link tests

When each Phase ships, the relevant test file should be moved back to
`tests/frontend/` and updated to match the new component signatures.

## Until then

These tests do NOT run (Vitest's `include` glob is `tests/frontend/**/*.test.{js,jsx,ts,tsx}`
which would normally pick them up, but they're under `_legacy/` and will fail
on import). To explicitly exclude them, the Vitest config should be updated
to `exclude: ["**/_legacy/**"]` if the suite ever needs to scan this folder
for any reason.

## Currently active frontend tests

- `tests/frontend/responsive.test.jsx` — pure CSS rule assertions, framework-free
