# Concord Lite — Mission Control Dashboard · Handoff Doc

Paste this whole document into a fresh chat to resume work. Files to copy from this project:

## Files to copy (in order of importance)
1. **`index.html`** — the standalone, self-contained dashboard. Everything is inlined (CSS + data + React app). Open in a browser, it just works. **This is the only file you strictly need to keep developing.**
2. **`styles.css`** — extracted CSS (same content as inlined `<style>` in index.html). Useful if you want to split files apart again.
3. **`data.js`** — extracted fixture data (Run #041, agents, contracts, trace, violations, patches, test, report). Same content as the inlined `<script>` block.
4. **`app.jsx`** — extracted React component code. Same content as the inlined Babel `<script>`.
5. **`uploads/Concord_Lite_5_Page_Build_Document_Updated.pdf`** — original build spec.
6. **`uploads/Concord_Lite_Zone_A_Supplement_Target_Workflow.pdf`** — Zone A target workflow spec.

> Note: split files (`styles.css`, `data.js`, `app.jsx`) failed to load via relative URL in the preview environment (got 401 errors), so the working version is fully inlined into `index.html`. If you continue editing, keep editing `index.html` directly OR re-split and load via `<link>`/`<script>` if your environment allows it.

---

## What was built

A 6-screen dark-mode mission-control dashboard for Concord Lite — an AG2 multi-agent workflow contract→repair→regression layer. NASA flight ops aesthetic, monospace, dense, terminal-feel.

### Aesthetic (locked, do not deviate)
- Background `#0c0f0a` (dark olive-black)
- Surface `#13160f`, surface-2 `#181b13`
- Border `#242820`, border-2 `#2e3327`
- Gold (primary accent, instruments) `#c8b560`, dim gold `#8a7a3f`
- Sage (pass) `#7a9e7e`
- Brick (fail) `#b85c4a`
- Orange (warn) `#c4854a`
- Text primary `#d4ceb8` (warm off-white)
- Text-2 `#6b6b58`, text-3 `#4a4a3d`
- Font: monospace stack only (`ui-monospace, "SF Mono", Menlo, "DejaVu Sans Mono", Consolas, monospace`). No Google Fonts.

### Forbidden
- No blue, no purple anywhere
- No gradients
- No glow effects, drop shadows, neon
- No rounded pill buttons (max 2px radius)
- No emoji or icons (text + geometric squares only)
- No animations except: (a) single blinking gold cursor on the active status line, (b) opacity pulse on running pipeline nodes during replay

### Required
- 1px solid borders (not 0.5px)
- Square or 2px-max rounded corners
- Status indicators are filled SQUARES, never circles
- Numbers larger than labels
- Uppercase labels with wide letter-spacing (0.14–0.22em) for headers
- Horizontal rules as section dividers
- Dense info layout

---

## Architecture

### Data fixture (`data.js` / `window.CONCORD_DATA`)
Models a literature-review-assistant Run #041 with 4 intentional contract violations:

- `run` — id `RUN-041`, workflow `LITERATURE_REVIEW_ASSISTANT`, AutoPattern, GroupChatManager, operator `j.kowalski`
- `stats` — 4 violations / 5 agents run / 4 patches ready / 12 events / 1 tool event
- `agents[]` — 5 agents: `RES ResearcherAgent` (PASS), `CRT CriticAgent` (PASS), `VRF VerifierAgent` (FAIL — no tool_event), `RPT ReporterAgent` (FAIL — verified=0), `ACT ActionAgent` (FAIL — approval=pending)
- `contracts[]` — 5 contracts (EVIDENCE, TOOL, ROUTING, APPROVAL, SCHEMA). Schema passes; rest fail/warn.
- `trace[]` — 12 events with `step, ts, agent, type, ctx, status, flag` (flag = contract id like `C-EVD`)
- `violations[]` — 4 violations V-001..V-004 with severity, contract, expected, observed, failed_agent/step, evidence[]
- `patches[]` — 4 AG2-native patches: P-001 Guardrail (Reporter), P-002 ToolGate (Verifier), P-003 OnContextCondition (GroupChatManager), P-004 UserProxyAgent/HumanGate (ActionAgent). Each has `removed[]` and `added[]` code lines.
- `test` — Daytona sandbox `dt-9f3a-2b71`, pytest output lines, 4 PASS assertions
- `report` — summary paragraph, patches_applied list, approval block (`PENDING_OPERATOR`)

### React component layout (`app.jsx`)
- `<App>` — root state: `screen` (current tab id), `selectedPatch` (filter for repair screen)
- `<TopBar>` — brand · 6 plain-text tabs (active has gold bottom-border) · `<StatusCluster>`
- `<StatusCluster>` — top-right text. Says **"4 VIOLATIONS DETECTED"** on every screen except `report`, where it swaps to **"RERUN READY"** (sage). Has the single blinking gold cursor.
- `<MetaStrip>` — 6-cell run metadata strip below tabs
- `<PipelineGraph>` — **NEW** SVG graph of the 5 agents with replay controls (see below)
- `<Overview>` — 3 stat blocks · pipeline graph · Contract Status list + Run Task card
- `<Trace>` — full 12-row event timeline table
- `<Violations>` — 4 severity-bar rows (clickable → repair patch) + Evidence Chain table
- `<Repair>` — 4 diff blocks (red - / green + columns, line-prefixed). Filter buttons: ALL · P-001 · P-002 · P-003 · P-004. Clicking a violation row from screen 3 jumps here with that patch pre-selected.
- `<Regression>` — Daytona terminal stream + Sandbox card + Assertions table
- `<Report>` — Executive Summary + Approval block (PENDING_OPERATOR, orange) + Patches Applied table + Verification card with EXPORT JSON / VIEW TEST buttons

### Wiring
- Clicking any node in `<PipelineGraph>` → navigate to `trace` screen
- Clicking any violation row → set `selectedPatch` to matching patch and navigate to `repair`
- Top-right status text auto-switches to "RERUN READY" on report screen

---

## The Pipeline Graph (most recent addition)

`<PipelineGraph>` lives at the top of Overview. Replaces the old static row of 5 boxes with an SVG graph that animates through the run.

### Layout
- 5 nodes on a horizontal rail at y=96 in a 1200×240 viewBox
- Each node = outer ring rect (40×40) + inner fill rect (24×24), both squares
- Step badge `01 · RES` above, agent name + status (RUNNING/PASS/FAIL/PENDING) below
- Per-agent step ticks below the name (Researcher = 4 ticks, etc.)
- Edges between nodes with arrowheads pointing right; "handoff" sublabel above each
- Live ctx line at bottom showing current step's `key=value` pairs (turns brick if FAIL)

### State logic
- `AGENT_STEP_MAP` pins which trace step IDs belong to each agent: RES=[2,3,4,5], CRT=[6,7], VRF=[8,9,10], RPT=[11], ACT=[12]
- `agentStateAt(agentId, currentStep)` returns one of: `idle` (before agent's first step), `run` (mid-execution), `pass` / `fail` / `warn` (after last step, based on worst event status seen)
- `edgeStateAt(fromIdx, currentStep)` returns: `idle` (both not started), `active` (handoff in flight, gold), or the source agent's resolved status color

### Color tokens (no gradients)
- `idle` → text-3 outline, transparent fill
- `run` → gold ring + gold fill, with `nodePulse` 50% opacity animation
- `pass` → sage ring + sage fill
- `fail` → brick ring + brick fill
- `warn` → orange

### Replay controls
- `▶ REPLAY RUN` (gold-bordered) — resets step to 0, starts auto-play
- `▶ PLAY` / `❚❚ PAUSE` — toggle, ~520ms per step
- `■ END STATE` — jump to step 12 (final state)
- Step readout `STEP NN / 12` + live timestamp + `Agent.event_type` of current step
- Legend on the right with idle/run/pass/fail squares

### Footer
- 5-cell row under the SVG showing `AGENT_ID · X/Y STEPS` and the agent's note (e.g. "no tool_event")

---

## Build doc reference (4-min demo path)

`workflow under test → contract violation → repair → regression test`

The 4 violations the run intentionally exhibits:
1. **Missing evidence** — Verifier sets `verified_sources_count=0`, Reporter still emits final output. Repair: evidence Guardrail on Reporter.
2. **Tool claim without tool_event** — Verifier says "I verified..." but no Tavily/Daytona event recorded. Repair: ToolGate requires last tool_event ok before verdict.
3. **Routing skip** — Reporter handoff happens despite no successful tool event. Repair: OnContextCondition on Handoff.
4. **Side effect without approval** — ActionAgent runs save_report with approval_status=pending. Repair: insert UserProxyAgent / HumanGate before ActionAgent.

Sponsors visible in the UI: **Daytona** (regression sandbox `dt-9f3a-2b71`), **Tavily** (referenced in researcher tool_call). Backend can be partially simulated; UI is fully built and demo-ready.

---

## Likely next requests
- Wire up real Zone B `/api/analyze` endpoint and replace `data.js` fixture with live fetch
- Add Tavily evidence panel (sources retrieved + which were verified)
- Add a "trace timeline" mini-graph on the Trace screen (vertical, similar idiom)
- Approve & Rerun button should trigger a re-run animation on the pipeline graph
- Export JSON button on the Report screen
- Workflow Detail / DAG screen showing the GroupChatManager handoff topology vs the actual trace path

---

## How to resume on a new machine

1. Drop the listed files into a project root (just `index.html` is enough to view).
2. Open `index.html` in any modern browser — no build, no server needed.
3. To edit: open `index.html` and find the appropriate section by these markers in the comments:
   - `/* ---------- Pipeline graph ---------- */` (CSS for the new graph)
   - `/* ---------------- PIPELINE GRAPH ---------------- */` (JSX component)
   - `/* ---------------- OVERVIEW ---------------- */` etc. for each screen
4. The fixture is `window.CONCORD_DATA` — search for it and edit in place.
5. If you split files again, paths must work from the same directory as the HTML file.

That's the full state. Hand this doc + `index.html` to the next chat and you're set.
