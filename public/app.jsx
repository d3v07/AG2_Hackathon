/* global React, ReactDOM */
const { useState, useEffect, useMemo } = React;
const BOOT_DATA = window.CONCORD_DATA;

function normalizeDashboardData(data, options = {}) {
  const source = data || {};
  const fallbackFixture = options.fallbackFixture !== false;
  const fixture = fallbackFixture ? BOOT_DATA : {};
  const emptyTest = { name: "pending", runner: "", sandbox_id: "", duration_ms: 0, lines: [], assertions: [] };
  const emptyCost = { daytona_seconds: 0, llm_tokens: 0, llm_cost_usd: 0, daytona_cost_usd: 0 };
  const sourceReport = source.report || {};
  const fixtureReport = fixture.report || {};
  const cost = {
    ...emptyCost,
    ...(fixture.cost || fixtureReport.cost_summary || {}),
    ...(source.cost || sourceReport.cost_summary || {}),
  };
  const emptyReport = {
    summary: "",
    patches_applied: [],
    usage_summary: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
    cost_summary: emptyCost,
    approval: { status: "UNAVAILABLE", operator: "", requested_at: "", sla: "" },
  };
  const report = {
    ...emptyReport,
    ...fixtureReport,
    ...sourceReport,
    usage_summary: {
      ...emptyReport.usage_summary,
      ...(fixtureReport.usage_summary || {}),
      ...(sourceReport.usage_summary || {}),
    },
    cost_summary: cost,
  };
  return {
    ...source,
    run: { ...(fixture.run || {}), ...(source.run || {}) },
    stats: { ...(fixture.stats || {}), ...(source.stats || {}) },
    cost,
    agents: Array.isArray(source.agents) ? source.agents : (fixture.agents || []),
    topology: source.topology || fixture.topology || { entry: "", nodes: [], edges: [] },
    routes: Array.isArray(source.routes) ? source.routes : (fixture.routes || []),
    recurrences: Array.isArray(source.recurrences) ? source.recurrences : (fixture.recurrences || []),
    contracts: Array.isArray(source.contracts) ? source.contracts : (fixture.contracts || []),
    trace: Array.isArray(source.trace) ? source.trace : (fixture.trace || []),
    violations: Array.isArray(source.violations) ? source.violations : (fixture.violations || []),
    patches: Array.isArray(source.patches) ? source.patches : (fixture.patches || []),
    test: { ...(fixture.test || emptyTest), ...(source.test || {}) },
    report,
    status: source.status || fixture.status || "queued",
    error: source.error || "",
  };
}

function liveHeaders() {
  const headers = {};
  if (window.CONCORD_TENANT_ID) headers["X-Tenant-ID"] = window.CONCORD_TENANT_ID;
  if (window.CONCORD_API_KEY) {
    headers["Authorization"] = `Bearer ${window.CONCORD_API_KEY}`;
    headers["X-Concord-API-Key"] = window.CONCORD_API_KEY;
  }
  return headers;
}

async function openStreamToken(liveRunId, headers) {
  const response = await fetch(`/api/runs/${liveRunId}/events/token`, {
    method: "POST",
    headers,
  });
  if (!response.ok) throw new Error(`event token failed: ${response.status}`);
  const payload = await response.json();
  return payload.stream_token;
}

const FIXTURE_DATA = normalizeDashboardData(window.CONCORD_DATA, { fallbackFixture: true });
let D = FIXTURE_DATA;

const SCREENS = [
  { id: "overview",   num: "01", label: "Overview" },
  { id: "topology",   num: "02", label: "Workflow DAG" },
  { id: "trace",      num: "03", label: "Agent Trace" },
  { id: "violations", num: "04", label: "Violations" },
  { id: "repair",     num: "05", label: "Repair Patch" },
  { id: "regression", num: "06", label: "Regression" },
  { id: "report",     num: "07", label: "Final Report" },
];

function Sq({ kind }) { return <span className={`sq ${kind}`}></span>; }
function Pill({ kind, children }) {
  return <span className={`pill ${kind}`}><Sq kind={kind} />{children}</span>;
}

function sourceBadgeText(sourceMode, connectionState, liveStatus) {
  if (sourceMode === "fixture") return "FIXTURE";
  if (connectionState === "connecting") return "LIVE CONNECTING";
  if (connectionState === "error") return "LIVE ERROR";
  return `LIVE ${String(liveStatus || "CONNECTED").toUpperCase()}`;
}

function StatusCluster({ screen, sourceMode, setSourceMode, connectionState, liveStatus }) {
  const onReport = screen === "report";
  const violations = D.stats?.violations || 0;
  const text = onReport ? "RERUN READY" : `${violations} VIOLATION${violations === 1 ? "" : "S"} DETECTED`;
  const klass = onReport || violations === 0 ? "ok" : "fail";
  const dot = sourceMode === "live" && connectionState === "connecting" ? "warn" : klass;
  return (
    <div className="status-cluster">
      <div className="source-toggle" aria-label="data source">
        <button
          className={`source-btn ${sourceMode === "fixture" ? "active" : ""}`}
          onClick={() => setSourceMode("fixture")}
        >
          Fixture
        </button>
        <button
          className={`source-btn ${sourceMode === "live" ? "active" : ""}`}
          onClick={() => setSourceMode("live")}
        >
          Live
        </button>
      </div>
      <div className="status-line">
        <span className={`status-dot ${dot}`}></span>
        <span className={`status-text ${klass}`}>{text}</span>
        <span className="cursor"></span>
      </div>
      <div className={`source-badge ${sourceMode} ${connectionState}`}>
        {sourceBadgeText(sourceMode, connectionState, liveStatus)}
      </div>
      <div className="status-line muted" style={{fontSize: 11, letterSpacing: "0.14em"}}>
        {D.run?.started ? D.run.started.replace("T", " ").replace("Z", " UTC") : "time unavailable"}
      </div>
    </div>
  );
}

function TopBar({ screen, setScreen, sourceMode, setSourceMode, connectionState, liveStatus }) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="mark">CONCORD · LITE</div>
        <div className="sub">CONTRACT &nbsp;&middot;&nbsp; REPAIR &nbsp;&middot;&nbsp; REGRESSION</div>
      </div>
      <nav className="tabs">
        {SCREENS.map(s => (
          <button
            key={s.id}
            className={`tab ${screen === s.id ? "active" : ""}`}
            onClick={() => setScreen(s.id)}
          >
            <span className="num">{s.num}</span>
            <span>{s.label}</span>
          </button>
        ))}
      </nav>
      <StatusCluster
        screen={screen}
        sourceMode={sourceMode}
        setSourceMode={setSourceMode}
        connectionState={connectionState}
        liveStatus={liveStatus}
      />
    </header>
  );
}

function MetaStrip({ sourceMode, connectionState }) {
  const r = D.run;
  return (
    <div className="meta-strip">
      <div className="meta-cell"><span className="lbl">Run</span><span className="val">{r.id}</span></div>
      <div className="meta-cell"><span className="lbl">Workflow</span><span className="val">{r.workflow}</span></div>
      <div className="meta-cell"><span className="lbl">Pattern</span><span className="val">{r.pattern}</span></div>
      <div className="meta-cell"><span className="lbl">Manager</span><span className="val">{r.manager}</span></div>
      <div className="meta-cell"><span className="lbl">Duration</span><span className="val">{(r.duration_ms/1000).toFixed(2)}s</span></div>
      <div className="meta-cell"><span className="lbl">Operator</span><span className="val">{r.operator}</span></div>
      <div className="meta-cell"><span className="lbl">Source</span><span className="val">{sourceMode.toUpperCase()} · {connectionState.toUpperCase()}</span></div>
    </div>
  );
}

/* ---------------- PIPELINE GRAPH ---------------- */
const FIRST_STEP = 1;

function eventBelongsToAgent(agent, event) {
  const eventAgent = String(event?.agent || "");
  const agentName = String(agent?.name || "");
  const agentId = String(agent?.id || "");
  const shortName = agentName.replace(/Agent$/, "");
  return eventAgent === agentName
    || eventAgent === agentId
    || (!!shortName && eventAgent.startsWith(shortName));
}

function buildAgentStepMap(agents, trace) {
  const stepMap = {};
  agents.forEach(agent => {
    stepMap[agent.id] = trace
      .filter(event => eventBelongsToAgent(agent, event))
      .map(event => Number(event.step))
      .filter(Number.isFinite);
  });
  return stepMap;
}

function agentStateAt(agentId, currentStep, stepMap, trace) {
  const range = stepMap[agentId] || [];
  if (!range.length) return "idle";
  const start = range[0], end = range[range.length - 1];
  if (currentStep < start) return "idle";
  if (currentStep >= start && currentStep < end) return "run";
  const events = trace.filter(e => range.includes(Number(e.step)) && Number(e.step) <= currentStep);
  if (events.some(e => e.status === "FAIL")) return "fail";
  if (events.some(e => e.status === "WARN")) return "warn";
  return "pass";
}

function edgeStateAt(fromIdx, currentStep, agents, stepMap, trace) {
  const fromId = agents[fromIdx]?.id;
  const toId = agents[fromIdx + 1]?.id;
  const fromRange = stepMap[fromId] || [];
  const toRange = stepMap[toId] || [];
  if (!fromRange.length || !toRange.length) return "idle";
  const fromEnd = fromRange[fromRange.length - 1];
  const toStart = toRange[0];
  if (currentStep < fromEnd) return "idle";
  if (currentStep >= fromEnd && currentStep < toStart) return "active";
  const fs = agentStateAt(fromId, currentStep, stepMap, trace);
  return fs;
}

function PipelineGraph({ setScreen }) {
  const trace = Array.isArray(D.trace) ? D.trace : [];
  const agents = Array.isArray(D.agents) && D.agents.length
    ? D.agents
    : [{
        id: "RUN",
        name: D.run?.workflow || "Run",
        steps: trace.length,
        status: D.status === "failed" ? "FAIL" : "PASS",
        note: D.status || "pending",
      }];
  const stepMap = useMemo(() => buildAgentStepMap(agents, trace), [agents, trace]);
  const totalSteps = Math.max(...trace.map(e => Number(e.step) || 0), trace.length, 1);
  const [step, setStep] = useState(totalSteps);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(380); // demo: faster than the original 520ms
  const [subStep, setSubStep] = useState(1); // 0..1 progress between step-1 and step

  useEffect(() => {
    if (step > totalSteps) setStep(totalSteps);
    if (!playing && step < totalSteps) setStep(totalSteps);
  }, [step, totalSteps, playing]);

  useEffect(() => {
    if (!playing) return;
    if (step >= totalSteps) { setPlaying(false); return; }
    const t = setTimeout(() => setStep(s => s + 1), speed);
    return () => clearTimeout(t);
  }, [playing, step, speed, totalSteps]);

  // Animate subStep 0 → 1 across each step transition for smooth traveler motion
  useEffect(() => {
    setSubStep(0);
    let raf;
    const start = performance.now();
    const dur = playing ? speed : 320;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / dur);
      setSubStep(t);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [step]);

  const replay = () => { setStep(0); setPlaying(true); };
  const togglePlay = () => {
    if (step >= totalSteps) { setStep(0); setPlaying(true); }
    else setPlaying(p => !p);
  };
  const reset = () => { setPlaying(false); setStep(totalSteps); };

  // Stage shortcut: R replays. Ignore if user is typing.
  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea") return;
      if (e.key === "r" || e.key === "R") { replay(); }
      if (e.key === " ") { e.preventDefault(); togglePlay(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, playing]);

  // Layout
  const W = 1200, H = 260;
  const nodeY = 116;
  const nodeXs = agents.map((_, i) => 90 + i * ((W - 180) / Math.max(agents.length - 1, 1)));

  const currentEvent = trace.find(e => Number(e.step) === step);
  const ctxLine = currentEvent
    ? Object.entries(currentEvent.ctx || {}).map(([k,v]) => `${k}=${typeof v === "string" ? `"${v}"` : v}`).join("  ·  ")
    : "";

  const stateColor = {
    idle: "var(--text-3)",
    run:  "var(--gold)",
    pass: "var(--sage)",
    fail: "var(--brick)",
    warn: "var(--orange)",
    active: "var(--gold)",
  };

  return (
    <div className="pgraph-wrap" style={{marginBottom: 22}}>
      <div className="pgraph-controls">
        <button className="ctl primary" onClick={replay}>▶ REPLAY RUN</button>
        <button className="ctl" onClick={togglePlay}>{playing ? "❚❚ PAUSE" : "▶ PLAY"}</button>
        <button className="ctl" onClick={reset}>■ END STATE</button>
        <span className="step-readout">STEP {String(step).padStart(2,"0")} / {String(totalSteps).padStart(2,"0")}</span>
        <span className="muted" style={{fontSize: 10.5}}>
          {currentEvent ? `${currentEvent.ts}  ${currentEvent.agent}.${currentEvent.type}` : "session not started"}
        </span>
        <span className="kbd-hint" style={{marginLeft: 14}}>
          <kbd>R</kbd> REPLAY <kbd>SPACE</kbd> PLAY
        </span>
        <span style={{marginLeft: 10, display: "flex", gap: 4}}>
          {[{l:"1×",v:520},{l:"2×",v:260},{l:"4×",v:130}].map(s => (
            <button key={s.l} className="ctl" style={{padding: "3px 8px",
              borderColor: speed === s.v ? "var(--gold)" : "var(--border-2)",
              color: speed === s.v ? "var(--gold)" : "var(--text)"}}
              onClick={() => setSpeed(s.v)}>{s.l}</button>
          ))}
        </span>
        <span className="legend">
          <span className="lg"><span className="sq idle"></span><span>IDLE</span></span>
          <span className="lg"><span className="sq run"></span><span>RUN</span></span>
          <span className="lg"><span className="sq pass"></span><span>PASS</span></span>
          <span className="lg"><span className="sq fail"></span><span>FAIL</span></span>
        </span>
      </div>

      <svg className="pgraph-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {/* baseline rail */}
        <line x1={nodeXs[0]} y1={nodeY} x2={nodeXs[nodeXs.length-1]} y2={nodeY} className="edge" />
        {/* edges */}
        {agents.slice(0, -1).map((a, i) => {
          const st = edgeStateAt(i, step, agents, stepMap, trace);
          const x1 = nodeXs[i] + 20, x2 = nodeXs[i+1] - 20;
          const cls = `edge ${st}`;
          return (
            <g key={`e-${i}`}>
              <line x1={x1} y1={nodeY} x2={x2} y2={nodeY} className={cls} />
              {/* arrow head */}
              <polyline
                points={`${x2-6},${nodeY-4} ${x2},${nodeY} ${x2-6},${nodeY+4}`}
                fill="none" stroke={stateColor[st] || "var(--text-3)"} strokeWidth="1"
              />
              {/* handoff tick label */}
              <text x={(x1+x2)/2} y={nodeY - 12} textAnchor="middle" className="sublabel">
                handoff
              </text>
            </g>
          );
        })}
        {/* nodes */}
        {agents.map((a, i) => {
          const st = agentStateAt(a.id, step, stepMap, trace);
          const cx = nodeXs[i];
          const ticks = stepMap[a.id] || [];
          return (
            <g key={a.id} style={{cursor: "pointer"}} onClick={() => setScreen("trace")}>
              {/* outer square ring */}
              <rect
                x={cx-20} y={nodeY-20} width="40" height="40"
                className={`node-ring ${st}`}
              />
              {/* inner fill (smaller square) — solid status fill, no gradients */}
              <rect
                x={cx-12} y={nodeY-12} width="24" height="24"
                className={`node-fill ${st} ${st === "run" ? "run-pulse" : ""}`}
              />
              {/* step badge */}
              <text x={cx} y={nodeY-30} textAnchor="middle" className="sublabel">
                {String(i+1).padStart(2,"0")} · {a.id}
              </text>
              {/* agent name */}
              <text x={cx} y={nodeY+42} textAnchor="middle" className="label">
                {a.name.replace("Agent","")}
              </text>
              <text x={cx} y={nodeY+56} textAnchor="middle" className="sublabel">
                {st === "idle" ? "PENDING" : st === "run" ? "RUNNING" : st.toUpperCase()}
              </text>
              {/* per-step ticks under each node */}
              {ticks.map((s, j) => (
                <line key={s}
                  x1={cx - (ticks.length-1)*4 + j*8}
                  y1={nodeY+72}
                  x2={cx - (ticks.length-1)*4 + j*8}
                  y2={nodeY+78}
                  className={`step-tick ${s === step ? "now" : ""}`}
                  stroke={s <= step ? (s === step ? "var(--gold)" : stateColor[st]) : "var(--border)"}
                />
              ))}
            </g>
          );
        })}
        {/* current-event ctx readout */}
        {currentEvent && (
          <text x={W/2} y={H-14} textAnchor="middle" className={`ctx-line ${currentEvent.status === "FAIL" ? "bad" : ""}`}>
            {ctxLine.length > 130 ? ctxLine.slice(0,128) + "…" : ctxLine}
          </text>
        )}

        {/* TRAVELER — context envelope flying from MGR → ACT during replay.
            Position is interpolated from the current step's owning agent into
            the next event's owning agent. Color flips to brick if a violation
            fires at this step. */}
        {step > 0 && step <= totalSteps && (() => {
          const agentIdxOf = (agentName) => {
            const i = agents.findIndex(a => eventBelongsToAgent(a, { agent: agentName }));
            return i;
          };
          const ev = trace.find(e => Number(e.step) === step) || trace[trace.length-1] || {};
          const prevEv = trace.find(e => Number(e.step) === step - 1);
          const fromIdx = prevEv ? agentIdxOf(prevEv.agent) : 0;
          const toIdx = agentIdxOf(ev.agent);
          // If either agent isn't on the rail (e.g. GroupChatManager step_1),
          // anchor to first node.
          const a = fromIdx < 0 ? 0 : fromIdx;
          const b = toIdx < 0 ? a : toIdx;
          // Ease-in-out
          const t = subStep < 0.5 ? 2*subStep*subStep : 1 - Math.pow(-2*subStep+2, 2)/2;
          const x = nodeXs[a] + (nodeXs[b] - nodeXs[a]) * t;
          const y = nodeY - 38; // float just above the nodes
          // Cumulative health: once any prior step has FAILed, traveler stays brick.
          // WARN tints orange; otherwise gold.
          const priorEvents = trace.filter(e => Number(e.step) <= step);
          const priorFailed = priorEvents.some(e => e.status === "FAIL");
          const priorWarned = priorEvents.some(e => e.status === "WARN");
          const isFail = priorFailed || ev.status === "FAIL";
          const isWarn = !isFail && (priorWarned || ev.status === "WARN");
          const color = isFail ? "var(--brick)" : isWarn ? "var(--orange)" : "var(--gold)";
          // Short label of what's traveling
          const labelMap = {
            session_start: "INIT",
            agent_turn:    "TURN",
            tool_call:     "TOOL",
            context_write: "WRITE",
            handoff:       "HANDOFF",
            side_effect:   "EFFECT",
          };
          const flowLabel = labelMap[ev.type] || "CTX";
          // Tail dots — three faint trailing markers, fading
          const tailOffsets = [16, 32, 48];
          return (
            <g>
              {/* leader line down to the rail */}
              <line x1={x} y1={y+10} x2={x} y2={nodeY-22}
                stroke={color} strokeWidth="1" strokeDasharray="2 3" opacity="0.5" />
              {/* trailing dots */}
              {tailOffsets.map((dx, i) => {
                const dir = b >= a ? -1 : 1;
                const tx = x + dir * dx;
                if (tx < nodeXs[0] - 20 || tx > nodeXs[nodeXs.length-1] + 20) return null;
                return (
                  <rect key={i} x={tx-2} y={y-2} width="4" height="4"
                    fill={color} opacity={0.35 - i*0.1} />
                );
              })}
              {/* glow square + envelope */}
              <rect x={x-32} y={y-14} width="64" height="28" className="traveler-glow"
                style={{fill: color, opacity: 0.18}} />
              <rect x={x-28} y={y-11} width="56" height="22" className="traveler-rect"
                style={{stroke: color, fill: "var(--surface)"}} />
              <text x={x} y={y+4} textAnchor="middle" className="traveler-label"
                style={{fill: color}}>
                {flowLabel}
              </text>
              {/* subtle pulse */}
              <circle cx={x} cy={y} className="traveler-pulse" style={{stroke: color}} />
            </g>
          );
        })()}
      </svg>

      <div className="pgraph-foot">
        {agents.map(a => {
          const st = agentStateAt(a.id, step, stepMap, trace);
          const ticks = stepMap[a.id] || [];
          return (
            <div key={a.id} className="cell">
              <span className="ev">{a.id} · {st === "idle" ? "—" : `${ticks.filter(s => s <= step).length}/${Math.max(ticks.length, 1)} STEPS`}</span>
              <span className="ag">{a.note}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function costMetric(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function formatUsd(value) {
  const amount = costMetric(value);
  if (amount === 0) return "$0.00";
  if (amount < 0.01) return `$${amount.toFixed(5)}`;
  return `$${amount.toFixed(2)}`;
}

function formatSeconds(value) {
  return `${costMetric(value).toFixed(2)}s`;
}

function CostPanel({ usage }) {
  const runCost = D.cost || D.report?.cost_summary || {};
  const tenantUsage = usage || {};
  const llmCost = costMetric(runCost.llm_cost_usd);
  const daytonaCost = costMetric(runCost.daytona_cost_usd);
  const totalCost = costMetric(runCost.total_cost_usd, llmCost + daytonaCost);
  const runCount = tenantUsage.run_count ?? 1;
  return (
    <div className="card" style={{width: 360}}>
      <div className="card-head">
        <span>Run Cost</span>
        <span className="right">tenant total: {runCount} run{runCount === 1 ? "" : "s"}</span>
      </div>
      <div className="card-body">
        <div className="cost-grid">
          <div className="cost-metric total">
            <div className="lbl">Total Cost</div>
            <div className="val">{formatUsd(totalCost)}</div>
          </div>
          <div className="cost-metric">
            <div className="lbl">LLM Tokens</div>
            <div className="val">{Number(runCost.llm_tokens ?? 0).toLocaleString()}</div>
          </div>
          <div className="cost-metric">
            <div className="lbl">Daytona Time</div>
            <div className="val">{formatSeconds(runCost.daytona_seconds)}</div>
          </div>
          <div className="cost-metric">
            <div className="lbl">Daytona Cost</div>
            <div className="val">{formatUsd(daytonaCost)}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------------- OVERVIEW ---------------- */
function Overview({ setScreen, tenantUsage }) {
  return (
    <>
      <div className="section-head">
        <h2>Run Summary &nbsp;//&nbsp; {D.run.id} &nbsp;&middot;&nbsp; {D.run.workflow}</h2>
        <div className="right">started 14:22:08 UTC &nbsp;&middot;&nbsp; trace nominal</div>
      </div>

      <div className="stat-grid" style={{marginBottom: 22}}>
        <div className="stat">
          <div className="stat-accent brick"></div>
          <div className="lbl">Contract Violations</div>
          <div className="num brick">{D.stats.violations}</div>
          <div className="delta">3 HIGH &nbsp;/&nbsp; 1 MED &nbsp;/&nbsp; 0 LOW</div>
        </div>
        <div className="stat">
          <div className="stat-accent gold"></div>
          <div className="lbl">Agents Run</div>
          <div className="num gold">{D.stats.agents_run}</div>
          <div className="delta">{D.stats.events_total} events &nbsp;&middot;&nbsp; {D.stats.tool_events} tool event</div>
        </div>
        <div className="stat">
          <div className="stat-accent sage"></div>
          <div className="lbl">Repair Ready</div>
          <div className="num sage">{D.stats.repair_ready} <span style={{color: "var(--text-3)", fontSize: 16}}>/ {D.stats.violations}</span></div>
          <div className="delta">AG2 primitives mapped &nbsp;&middot;&nbsp; 4 PATCHES</div>
        </div>
      </div>

      <div className="section-head">
        <h2>Agent Pipeline &nbsp;//&nbsp; live execution graph</h2>
        <div className="right">replay run · click any node to inspect trace</div>
      </div>
      <PipelineGraph setScreen={setScreen} />

      <div className="row" style={{alignItems: "stretch"}}>
        <div className="card grow">
          <div className="card-head">
            <span>Contract Status</span>
            <span className="right">{D.stats.contracts_passed} / {D.stats.contracts_total} passing</span>
          </div>
          <div className="contracts-list">
            {D.contracts.map(c => (
              <div key={c.id} className="row-c">
                <span className="id">{c.id}</span>
                <span className="ctype">{c.type}</span>
                <span className="rule">{c.rule}</span>
                <span><Pill kind={c.status.toLowerCase()}>{c.status}</Pill></span>
              </div>
            ))}
          </div>
        </div>
        <CostPanel usage={tenantUsage} />
        <div className="card" style={{width: 360}}>
          <div className="card-head"><span>Run Task</span><span className="right">user input</span></div>
          <div className="card-body">
            <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase", marginBottom: 8}}>Question</div>
            <div style={{lineHeight: 1.6, marginBottom: 14}}>{D.run.task}</div>
            <hr />
            <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 12, fontSize: 11.5}}>
              <div><div className="muted" style={{fontSize: 10, letterSpacing: "0.14em"}}>RETRIEVED</div><div>7 sources</div></div>
              <div><div className="muted" style={{fontSize: 10, letterSpacing: "0.14em"}}>VERIFIED</div><div className="text-brick">0 sources</div></div>
              <div><div className="muted" style={{fontSize: 10, letterSpacing: "0.14em"}}>HANDOFFS</div><div>4</div></div>
              <div><div className="muted" style={{fontSize: 10, letterSpacing: "0.14em"}}>APPROVAL</div><div className="text-brick">pending</div></div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ---------------- WORKFLOW DAG ---------------- */
// Layered layout: place each node in a lane (Y axis) and a column (X axis).
// Lanes group nodes by role so the topology reads top-to-bottom by stage.
const DAG_POSITIONS = {
  MGR: { col: 0, lane: 0 },
  RES: { col: 1, lane: 1 },
  TVL: { col: 2, lane: 0 },
  CRT: { col: 3, lane: 1 },
  VRF: { col: 4, lane: 1 },
  RPT: { col: 5, lane: 1 },
  HGT: { col: 6, lane: 2 },
  ACT: { col: 6, lane: 1 },
};
const LANE_LABELS = ["TOOLS / MANAGER", "AGENT FLOW", "GATES / APPROVALS"];

function routeStatusToCls(s) {
  return ({ ok: "ok", skipped_guard: "skip", missing_approval: "miss", unexpected: "prop" })[s] || "ok";
}

function recurrenceTitle(recurrence) {
  if (!recurrence) return "";
  const runs = Array.isArray(recurrence.sample_run_ids) ? recurrence.sample_run_ids.join(", ") : "";
  return [
    `${recurrence.count || 0} recurring violation(s)`,
    recurrence.rule || recurrence.contract || recurrence.contract_type || "",
    recurrence.last_seen ? `last seen ${recurrence.last_seen}` : "",
    runs ? `runs ${runs}` : ""
  ].filter(Boolean).join(" · ");
}

function recurrenceForEdge(edge, route, recurrences) {
  return (recurrences || []).find(item => {
    if (!item || Number(item.count || 0) < 2) return false;
    if (item.edge && item.edge.from === edge.from && item.edge.to === edge.to) return true;
    return false;
  });
}

function recurrenceForNode(node, recurrences) {
  return (recurrences || []).find(item => {
    if (!item || Number(item.count || 0) < 2) return false;
    if (item.failed_agent && (item.failed_agent === node.name || item.failed_agent === node.id)) return true;
    return Array.isArray(node.contracts) && item.contract && node.contracts.includes(item.contract);
  });
}

function Topology({ setScreen, setSelectedPatch }) {
  const topology = D.topology || {};
  const topologyNodes = Array.isArray(topology.nodes) && topology.nodes.length
    ? topology.nodes
    : [{ id: "RUN", name: D.run?.workflow || D.run?.id || "Run", role: "run", kind: "manager", contracts: [] }];
  const topologyEdges = Array.isArray(topology.edges) ? topology.edges : [];
  const routes = Array.isArray(D.routes) ? D.routes : [];
  const recurrences = Array.isArray(D.recurrences) ? D.recurrences : [];
  const W = Math.max(1240, topologyNodes.length * 150 + 140), H = 360;
  const colW = 150, colX0 = 70;
  const laneY = [40, 160, 280];
  const nodeW = 110, nodeH = 56;
  const nodeIndexById = {};
  topologyNodes.forEach((node, index) => { nodeIndexById[node.id] = index; });

  const laneFor = (node) => {
    if (node.kind === "manager" || node.kind === "tool") return 0;
    if (node.kind === "gate") return 2;
    return 1;
  };

  const pos = (id) => {
    const p = DAG_POSITIONS[id];
    if (p) return { x: colX0 + p.col * colW, y: laneY[p.lane] };
    const index = nodeIndexById[id] ?? 0;
    const node = topologyNodes[index] || {};
    return { x: colX0 + index * colW, y: laneY[laneFor(node)] };
  };

  // map declared edges → routes for status, fall back to declared-only style
  const routeByEdge = {};
  routes.forEach(r => { routeByEdge[`${r.from}->${r.to}`] = r; });

  const edgeStatus = (e) => {
    const r = routeByEdge[`${e.from}->${e.to}`];
    if (!e.declared && e.proposed) return "prop";
    if (!r) return "idle";
    return routeStatusToCls(r.status);
  };

  const nodeStatus = (n) => {
    if (n.proposed) return "gate";
    const ag = D.agents.find(a => a.id === n.id);
    if (ag) return ag.status === "FAIL" ? "fail" : "pass";
    return n.kind;
  };

  // Curved orthogonal-ish path; gentle S-curve
  const pathFor = (a, b) => {
    const ax = a.x + nodeW / 2, ay = a.y + nodeH / 2;
    const bx = b.x - nodeW / 2, by = b.y + nodeH / 2;
    if (Math.abs(ay - by) < 4) {
      return `M ${ax} ${ay} L ${bx} ${by}`;
    }
    const mx = (ax + bx) / 2;
    return `M ${ax} ${ay} C ${mx} ${ay}, ${mx} ${by}, ${bx} ${by}`;
  };

  return (
    <>
      <div className="section-head">
        <h2>Workflow DAG &nbsp;//&nbsp; declared topology vs observed path</h2>
        <div className="right">{topologyNodes.length} nodes &nbsp;&middot;&nbsp; {topologyEdges.length} edges &nbsp;&middot;&nbsp; {routes.filter(r=>r.status!=="ok").length} divergences</div>
      </div>

      <div className="dag-wrap" style={{marginBottom: 14}}>
        <div className="dag-head">
          <span>concord.topology.v1</span>
          <span className="muted" style={{textTransform: "none", letterSpacing: 0}}>workflow ← {D.run.workflow}</span>
          <div className="legend">
            <span className="lg"><span className="sq ok"></span>OK</span>
            <span className="lg"><span className="sq skip"></span>SKIPPED GUARD</span>
            <span className="lg"><span className="sq miss"></span>MISSING APPROVAL</span>
            <span className="lg"><span className="sq prop"></span>PROPOSED (P-004)</span>
          </div>
        </div>

        <svg className="dag-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
          {/* lane backgrounds */}
          {laneY.map((y, i) => (
            <g key={i}>
              <line x1={40} y1={y + nodeH/2} x2={W - 40} y2={y + nodeH/2} className="lane" />
              <text x={40} y={y - 8} className="node-id">{LANE_LABELS[i]}</text>
            </g>
          ))}

          {/* edges */}
          {topologyEdges.filter(e => !e.returns).map((e, i) => {
            const a = pos(e.from), b = pos(e.to);
            const st = edgeStatus(e);
            const r = routeByEdge[`${e.from}->${e.to}`];
            const recurrence = recurrenceForEdge(e, r, recurrences);
            const mid = { x: (a.x + b.x)/2 + nodeW/2, y: (a.y + b.y)/2 + nodeH/2 };
            const labelText =
              st === "skip" ? "SKIPPED GUARD"
              : st === "miss" ? "NO APPROVAL"
              : st === "prop" ? "PROPOSED"
              : e.kind.toUpperCase();
            return (
              <g key={`e-${i}`}>
                <path d={pathFor(a, b)} className={`edge ${st}`} markerEnd="url(#arr)" />
                <text x={mid.x} y={mid.y - 8} textAnchor="middle" className={`edge-label ${st}`}>
                  {labelText}
                </text>
                {r && r.contract && (
                  <text x={mid.x} y={mid.y + 12} textAnchor="middle" className="edge-label">
                    {r.contract}
                  </text>
                )}
                {recurrence && (
                  <g className="recurrence-badge">
                    <title>{recurrenceTitle(recurrence)}</title>
                    <rect x={mid.x - 44} y={mid.y + 20} width="88" height="15" rx="1" />
                    <text x={mid.x} y={mid.y + 31} textAnchor="middle">
                      RECURRING x{recurrence.count}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* arrowhead defs — one per color (no gradients, plain strokes) */}
          <defs>
            <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor"/>
            </marker>
          </defs>

          {/* nodes */}
          {topologyNodes.map(n => {
            const p = pos(n.id);
            const cls = nodeStatus(n);
            const failed = D.agents.find(a => a.id === n.id && a.status === "FAIL");
            const recurrence = recurrenceForNode(n, recurrences);
            return (
              <g key={n.id}
                 style={{cursor: "pointer"}}
                 onClick={() => {
                   if (n.contracts && n.contracts.length) {
                     // jump to the matching violation/patch when relevant
                     const v = D.violations.find(v => n.contracts.includes(v.contract));
                     if (v) {
                       const patch = D.patches.find(p => p.violation === v.id);
                       if (patch) setSelectedPatch(patch.id);
                       setScreen("repair");
                       return;
                     }
                   }
                   setScreen("trace");
                 }}>
                {recurrence && <title>{recurrenceTitle(recurrence)}</title>}
                <rect x={p.x - nodeW/2} y={p.y} width={nodeW} height={nodeH}
                      className={`node-rect ${n.kind} ${cls}`} rx="2" />
                <text x={p.x} y={p.y + 14} textAnchor="middle" className="node-id">
                  {n.id} · {n.kind.toUpperCase()}
                </text>
                <text x={p.x} y={p.y + 32} textAnchor="middle" className={`node-name ${failed ? "fail" : (cls === "pass" ? "pass" : "")}`}>
                  {n.name.replace("Agent","")}
                </text>
                <text x={p.x} y={p.y + 47} textAnchor="middle" className="node-role">
                  {n.role.toUpperCase()}
                </text>
                {recurrence && (
                  <g className="recurrence-badge">
                    <rect x={p.x - 39} y={p.y + nodeH + 8} width="78" height="15" rx="1" />
                    <text x={p.x} y={p.y + nodeH + 19} textAnchor="middle">
                      RECURRING x{recurrence.count}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="card">
        <div className="card-head">
          <span>Routes &nbsp;&middot;&nbsp; declared vs observed</span>
          <span className="right">{routes.length} edges &nbsp;&middot;&nbsp; click a divergence row for repair</span>
        </div>
        <div className="card-body" style={{padding: 0}}>
          <table className="tbl routes-tbl">
            <thead>
              <tr>
                <th style={{width: 60}}>ID</th>
                <th style={{width: 220}}>Edge</th>
                <th style={{width: 100}}>Declared</th>
                <th style={{width: 100}}>Observed</th>
                <th style={{width: 100}}>Contract</th>
                <th>Note</th>
                <th style={{width: 160}}>Status</th>
              </tr>
            </thead>
            <tbody>
              {routes.map(r => {
                const cls = routeStatusToCls(r.status);
                const v = r.contract && D.violations.find(v => v.contract === r.contract);
                const clickable = !!v;
                const recurrence = recurrenceForEdge({ from: r.from, to: r.to }, r, recurrences);
                return (
                  <tr key={r.id}
                      className={clickable ? "clickable" : ""}
                      onClick={() => {
                        if (!v) return;
                        const p = D.patches.find(p => p.violation === v.id);
                        if (p) setSelectedPatch(p.id);
                        setScreen("repair");
                      }}>
                    <td className="text-2">{r.id}</td>
                    <td><span className="text-gold">{r.from}</span> → <span className="text-gold">{r.to}</span></td>
                    <td>{r.declared ? "yes" : <span className="text-3">no</span>}</td>
                    <td>{r.observed ? "yes" : <span className="text-3">no</span>}</td>
                    <td className="text-2">{r.contract || "—"}</td>
                    <td className={cls === "miss" || cls === "skip" ? "text-orange" : "text-2"}>
                      {r.note || "—"}
                      {recurrence && (
                        <div className="recurrence-note" title={recurrenceTitle(recurrence)}>
                          RECURRING x{recurrence.count}
                        </div>
                      )}
                    </td>
                    <td><span className={`badge ${cls}`}>
                      {r.status.replace("_", " ").toUpperCase()}
                    </span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

/* ---------------- TRACE MINI-RAIL ---------------- */
function TraceMiniRail({ focusedStep, setFocusedStep }) {
  const trace = Array.isArray(D.trace) ? D.trace : [];
  const lanes = Array.isArray(D.agents) ? D.agents : [];
  const RAIL_H = 520;
  const PAD_T = 36, PAD_B = 30;
  const usable = RAIL_H - PAD_T - PAD_B;
  const stepY = (s) => PAD_T + ((s - 1) / Math.max(trace.length - 1, 1)) * usable;
  const laneX = (idx) => 70 + idx * 28;
  const laneOfAgent = (agentName) => {
    const ag = lanes.find(a => eventBelongsToAgent(a, { agent: agentName }));
    return ag ? lanes.indexOf(ag) : -1;
  };

  return (
    <div className="minirail">
      <div className="mh">Trace Rail</div>
      <svg viewBox={`0 0 200 ${RAIL_H}`} preserveAspectRatio="none">
        {/* lane verticals */}
        {lanes.map((a, i) => (
          <g key={a.id}>
            <line x1={laneX(i)} y1={PAD_T - 10} x2={laneX(i)} y2={RAIL_H - PAD_B + 10} className="lane-line" />
            <text x={laneX(i)} y={PAD_T - 16} textAnchor="middle" className="lane-label">{a.id}</text>
          </g>
        ))}

        {/* connections between consecutive events */}
        {trace.slice(0, -1).map((e, i) => {
          const next = trace[i + 1];
          const li = laneOfAgent(e.agent), lj = laneOfAgent(next.agent);
          if (li < 0 || lj < 0) return null;
          const cls = next.status === "FAIL" ? "fail" : next.status === "WARN" ? "warn" : "";
          return (
            <line key={`c-${i}`}
              x1={laneX(li)} y1={stepY(e.step)}
              x2={laneX(lj)} y2={stepY(next.step)}
              className={`conn ${cls}`} />
          );
        })}

        {/* event squares */}
        {trace.map(e => {
          const li = laneOfAgent(e.agent);
          if (li < 0) return null;
          const x = laneX(li), y = stepY(e.step);
          const cls =
            e.status === "FAIL" ? "fail" :
            e.status === "WARN" ? "warn" :
            e.status === "OK"   ? "ok" : "idle";
          const focused = focusedStep === e.step;
          return (
            <g key={e.step}
               className={`step ${cls} ${focused ? "active" : ""}`}
               onClick={() => setFocusedStep(e.step)}>
              <rect x={x - 5} y={y - 5} width={10} height={10} />
              <text x={20} y={y + 3} className="step-num">{String(e.step).padStart(2,"0")}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}


function Trace() {
  const [focusedStep, setFocusedStep] = useState(null);
  const renderCtx = (e) => {
    const entries = Object.entries(e.ctx || {});
    return entries.map(([k, v], i) => {
      const isBad = (k === "verified_sources_count" && v === 0) || (k === "approval_status" && v === "pending");
      return (
        <span key={k} className="kv">
          <b>{k}</b>=<span className={isBad ? "bad" : ""}>{typeof v === "string" ? `"${v}"` : String(v)}</span>
          {i < entries.length - 1 ? <span style={{color: "var(--text-3)"}}>{"  "}&middot;{"  "}</span> : null}
        </span>
      );
    });
  };
  return (
    <>
      <div className="section-head">
        <h2>Agent Trace &nbsp;//&nbsp; ordered timeline</h2>
        <div className="right">{D.trace.length} events &nbsp;&middot;&nbsp; 1 tool event &nbsp;&middot;&nbsp; 4 violations</div>
      </div>
      <div className="trace-layout">
        <TraceMiniRail focusedStep={focusedStep} setFocusedStep={setFocusedStep} />
        <div className="card">
          <div className="card-head">
            <span>events</span>
            <span className="right">step &nbsp;&middot;&nbsp; ts &nbsp;&middot;&nbsp; agent &nbsp;&middot;&nbsp; type &nbsp;&middot;&nbsp; ctx &nbsp;&middot;&nbsp; status</span>
          </div>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{width: 36}}>#</th>
                <th style={{width: 110}}>Timestamp</th>
                <th style={{width: 180}}>Agent</th>
                <th style={{width: 140}}>Event</th>
                <th>Context</th>
                <th style={{width: 130}}>Status</th>
              </tr>
            </thead>
            <tbody>
              {D.trace.map(e => (
                <tr key={e.step}
                    onClick={() => setFocusedStep(e.step)}
                    className={`trace-row ${e.status === "FAIL" ? "fail" : e.status === "WARN" ? "warn" : ""} ${focusedStep === e.step ? "focused" : ""}`}
                    style={{cursor: "pointer"}}>
                  <td>{String(e.step).padStart(2, "0")}</td>
                  <td className="ts">{e.ts}</td>
                  <td><span className="agent">{e.agent}</span></td>
                  <td><span className="type">{e.type}</span></td>
                  <td className="ctx">{renderCtx(e)}</td>
                  <td>
                    {e.status === "OK"   && <Pill kind="pass">PASS</Pill>}
                    {e.status === "FAIL" && <Pill kind="fail">FAIL · {e.flag}</Pill>}
                    {e.status === "WARN" && <Pill kind="warn">WARN · {e.flag}</Pill>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{marginTop: 12, color: "var(--text-3)", fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", display: "flex", justifyContent: "space-between"}}>
        <span>end of trace &nbsp;&middot;&nbsp; final_output emitted at step 11 &nbsp;&middot;&nbsp; side_effect attempted at step 12</span>
        <span className="kbd-hint">CLICK <kbd>RAIL</kbd> OR <kbd>ROW</kbd> TO FOCUS</span>
      </div>
    </>
  );
}

/* ---------------- VIOLATIONS ---------------- */
function Violations({ setScreen, setSelectedPatch }) {
  const onClick = (v) => {
    const p = D.patches.find(p => p.violation === v.id);
    if (p) setSelectedPatch(p.id);
    setScreen("repair");
  };
  return (
    <>
      <div className="section-head">
        <h2>Contract Violations &nbsp;//&nbsp; {D.violations.length} detected</h2>
        <div className="right">click row to view repair patch</div>
      </div>

      <div className="viol-list" style={{marginBottom: 14}}>
        <div className="viol-row" style={{background: "var(--bg)", cursor: "default"}}>
          <div className="sev-bar" style={{background: "var(--border-2)"}}></div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Severity</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Contract</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Title</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Expected / Observed</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Failed Agent · Step</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Patch</div>
        </div>
        {D.violations.map(v => {
          const patch = D.patches.find(p => p.violation === v.id);
          return (
            <div key={v.id} className={`viol-row ${v.severity === "MED" ? "med" : ""}`} onClick={() => onClick(v)}>
              <div className="sev-bar"></div>
              <div>
                <div className="id">{v.id}</div>
                <div style={{marginTop: 4}}><Pill kind={v.severity.toLowerCase()}>{v.severity}</Pill></div>
              </div>
              <div className="ctype">
                <div>{v.type}</div>
                <div className="muted" style={{fontSize: 10, marginTop: 4, letterSpacing: "0.14em"}}>{v.contract}</div>
              </div>
              <div className="title">{v.title}</div>
              <div className="exp">
                <span className="lbl">Expected</span>
                <div>{v.expected}</div>
                <span className="lbl">Observed</span>
                <div className="text-brick">{v.observed}</div>
              </div>
              <div className="where">
                <div className="agent">{v.failed_agent}</div>
                <div className="muted" style={{fontSize: 11, marginTop: 4}}>step <span className="step">{String(v.failed_step).padStart(2,"0")}</span></div>
              </div>
              <div>
                <div className="text-gold" style={{letterSpacing: "0.16em", fontSize: 11}}>{patch ? patch.id : "—"}</div>
                <div className="muted" style={{fontSize: 10.5, marginTop: 4, letterSpacing: "0.1em"}}>{patch ? patch.primitive : ""}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="card">
        <div className="card-head">
          <span>Evidence Chain</span>
          <span className="right">deterministic checker output</span>
        </div>
        <div className="card-body" style={{padding: 0}}>
          <table className="tbl">
            <thead>
              <tr><th style={{width: 80}}>ID</th><th>Citation</th></tr>
            </thead>
            <tbody>
              {D.violations.flatMap(v =>
                v.evidence.map((e, i) => (
                  <tr key={`${v.id}-${i}`}>
                    <td className="text-2">{v.id}</td>
                    <td>{e}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

/* ---------------- REPAIR ---------------- */

// Per-patch DAG specs — declarative so the SVG renderer is data-driven
const REPAIR_DAG_SPECS = {
  "P-001": {
    left:  { label: "VerifierAgent", sub: "verified=0",   status: "fail" },
    right: { label: "ReporterAgent", sub: "ran anyway",   status: "fail" },
    fix:   { label: "Guardrail",     sub: "verified > 0" },
    edges: { broken: "handoff · verified=0", a: "handoff", b: "if pass → else route_back" },
  },
  "P-002": {
    left:  { label: "TavilySearch",  sub: "tool_event",   status: "pass" },
    right: { label: "VerifierAgent", sub: "no gate",      status: "fail" },
    fix:   { label: "ToolGate",      sub: "last_event=ok" },
    edges: { broken: "no gate · skipped", a: "tool_event", b: "gated" },
  },
  "P-003": {
    left:  { label: "VerifierAgent", sub: "tool_events=0", status: "fail" },
    right: { label: "ReporterAgent", sub: "bypassed",      status: "fail" },
    fix:   { label: "OnContextCondition", sub: "tool_ok check" },
    edges: { broken: "unconditional handoff", a: "handoff", b: "condition=true" },
  },
  "P-004": {
    left:  { label: "ReporterAgent", sub: "emits output", status: "pass" },
    right: { label: "ActionAgent",   sub: "approval=pending", status: "fail" },
    fix:   { label: "HumanGate",     sub: "UserProxyAgent" },
    edges: { broken: "direct · no gate", a: "output", b: "approved" },
  },
};

function RepairMiniDAG({ patchId, state }) {
  // state: "idle" | "applying" | "applied"
  const spec = REPAIR_DAG_SPECS[patchId];
  if (!spec) return null;

  const showFix = state === "applying" || state === "applied";
  const leftCx = 80, rightCx = 520, fixCx = 300;
  const agentW = 116, agentH = 44;
  const fixW = 134, fixH = 36;
  const rowY = 50; // top of agent rect
  const fixY = 54; // top of fix rect (slightly inset)

  // left/right node colors depend on state — agents go sage when applied
  const leftStatus = state === "applied" ? "pass" : spec.left.status;
  const rightStatus = state === "applied" ? "pass" : spec.right.status;
  const leftSub  = state === "applied" ? "fixed" : spec.left.sub;
  const rightSub = state === "applied" ? "fixed" : spec.right.sub;

  // edge classes
  const edgeBroken = state === "idle";
  const edgeApplying = state === "applying";
  const edgeApplied = state === "applied";
  const edgeClass = edgeBroken ? "broken" : edgeApplying ? "applying" : "applied";

  // arrowhead defs use unique ids per state
  const arrowId = `rdag-arrow-${patchId}-${state}`;
  const arrowColor = edgeBroken ? "#C73A1F" : edgeApplied ? "#6B8A3F" : "#F1642E";

  // node rect helper
  const nodeRect = (cx, status, label, sub) => {
    const x = cx - agentW / 2;
    return (
      <g>
        <rect className={`n-rect ${status}`} x={x} y={rowY} width={agentW} height={agentH} rx={0} ry={0} />
        <rect className={`n-status ${status}`} x={x + 6} y={rowY + 6} width={7} height={7} />
        <text className={`n-label ${status}`} x={cx} y={rowY + 22} textAnchor="middle">{label}</text>
        <text className={`n-sub ${status}`}   x={cx} y={rowY + 35} textAnchor="middle">{sub}</text>
      </g>
    );
  };

  // edge midpoint y
  const edgeY = rowY + agentH / 2;

  return (
    <svg className="rdag-svg" viewBox="0 0 600 130" preserveAspectRatio="xMidYMid meet">
      <defs>
        <marker id={arrowId} markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L5,3 L0,6 z" fill={arrowColor} />
        </marker>
      </defs>

      {/* Edges */}
      {!showFix && (
        <g>
          {/* single broken edge straight across */}
          <line className={`e-line ${edgeClass}`}
                x1={leftCx + agentW/2} y1={edgeY}
                x2={rightCx - agentW/2 - 4} y2={edgeY}
                markerEnd={`url(#${arrowId})`} />
          {(() => {
            const lbl = spec.edges.broken;
            const cx = (leftCx + rightCx) / 2;
            // Wrap on " · " separator if present and long
            if (lbl.length > 18 && lbl.includes(" · ")) {
              const parts = lbl.split(" · ");
              return (
                <text className={`e-label ${edgeClass}`} x={cx} y={edgeY - 14} textAnchor="middle">
                  <tspan x={cx} dy="0">{parts[0]}</tspan>
                  <tspan x={cx} dy="10">· {parts.slice(1).join(" · ")}</tspan>
                </text>
              );
            }
            return (
              <text className={`e-label ${edgeClass}`} x={cx} y={edgeY - 8} textAnchor="middle">{lbl}</text>
            );
          })()}
        </g>
      )}
      {showFix && (
        <g>
          {/* left → fix */}
          <line className={`e-line ${edgeClass}`}
                x1={leftCx + agentW/2} y1={edgeY}
                x2={fixCx - fixW/2 - 4} y2={edgeY}
                markerEnd={`url(#${arrowId})`} />
          <text className={`e-label ${edgeClass}`}
                x={(leftCx + agentW/2 + fixCx - fixW/2) / 2}
                y={edgeY - 8} textAnchor="middle">
            {spec.edges.a}
          </text>
          {/* fix → right */}
          <line className={`e-line ${edgeClass}`}
                x1={fixCx + fixW/2} y1={edgeY}
                x2={rightCx - agentW/2 - 4} y2={edgeY}
                markerEnd={`url(#${arrowId})`} />
          {(() => {
            const lbl = spec.edges.b;
            const cx = (fixCx + fixW/2 + rightCx - agentW/2) / 2;
            // Long labels split onto two lines
            if (lbl.length > 14) {
              const parts = lbl.split(" → ");
              if (parts.length === 2) {
                return (
                  <text className={`e-label ${edgeClass}`} x={cx} y={edgeY - 14} textAnchor="middle" style={{fontSize: 8.5}}>
                    <tspan x={cx} dy="0">{parts[0]} →</tspan>
                    <tspan x={cx} dy="10">{parts[1]}</tspan>
                  </text>
                );
              }
            }
            return (
              <text className={`e-label ${edgeClass}`} x={cx} y={edgeY - 8} textAnchor="middle">{lbl}</text>
            );
          })()}
        </g>
      )}

      {/* Agents */}
      {nodeRect(leftCx, leftStatus, spec.left.label, leftSub)}
      {nodeRect(rightCx, rightStatus, spec.right.label, rightSub)}

      {/* Fix node — only when applying or applied */}
      {showFix && (
        <g className={state === "applying" ? "fix-pulse" : ""}>
          <rect className="n-rect fix"
                x={fixCx - fixW/2} y={fixY}
                width={fixW} height={fixH} rx={0} ry={0} />
          <text className="n-label fix" x={fixCx} y={fixY + 16} textAnchor="middle">{spec.fix.label}</text>
          <text className="n-sub fix"   x={fixCx} y={fixY + 28} textAnchor="middle">{spec.fix.sub}</text>
        </g>
      )}
    </svg>
  );
}

function RepairDAG({ patches, appliedPatches, setAppliedPatches, setScreen }) {
  const [applying, setApplying] = useState(null); // patchId currently in applying transition

  const stateOf = (id) => {
    if (applying === id) return "applying";
    if (appliedPatches.includes(id)) return "applied";
    return "idle";
  };

  const onApply = (id) => {
    if (stateOf(id) !== "idle") return;
    setApplying(id);
    setTimeout(() => {
      setAppliedPatches(prev => prev.includes(id) ? prev : [...prev, id]);
      setApplying(null);
    }, 1600);
  };

  const allApplied = patches.length > 0 && patches.every(p => appliedPatches.includes(p.id));

  return (
    <>
      {allApplied && (
        <div className="rdag-banner">
          <div>
            <div className="head">All patches applied — workflow corrected</div>
            <div className="sub">4 AG2 primitives inserted · ready for regression</div>
          </div>
          <button className="go" onClick={() => setScreen("regression")}>Run regression →</button>
        </div>
      )}
      <div className="rdag-stack">
        {patches.map(p => {
          const st = stateOf(p.id);
          const statusText =
            st === "applying" ? "Zone B patching..." :
            st === "applied"  ? "Patch applied" :
                                "Ready to apply";
          const btnText =
            st === "applying" ? "Applying..." :
            st === "applied"  ? "Applied" :
                                "Apply patch";
          return (
            <div key={p.id} className="rdag-card">
              <div className="rdag-head">
                <div className="id">{p.id}</div>
                <div className="ctitle">{p.title}</div>
                <div><span className="prim">{p.primitive}</span></div>
                <div>
                  <Pill kind={st === "applied" ? "pass" : "ok"}>
                    {st === "applied" ? "APPLIED" : st === "applying" ? "PATCHING" : "READY"}
                  </Pill>
                </div>
              </div>
              <div className="rdag-body">
                <RepairMiniDAG patchId={p.id} state={st} />
              </div>
              <div className="rdag-controls">
                <div className={`status ${st === "applied" ? "applied" : ""}`}>{statusText}</div>
                <button
                  className={`rdag-btn ${st}`}
                  disabled={st !== "idle"}
                  onClick={() => onApply(p.id)}
                >{btnText}</button>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

/* ---------------- REPAIR ---------------- */
function Repair({ selectedPatch, setSelectedPatch, appliedPatches, setAppliedPatches, setScreen }) {
  const visiblePatches = D.patches.filter(p => selectedPatch === null || selectedPatch === p.id);
  return (
    <>
      <div className="section-head">
        <h2>Repair Patch &nbsp;//&nbsp; AG2-native primitives</h2>
        <div className="right">{D.patches.length} patches &nbsp;&middot;&nbsp; mapped from {D.violations.length} violations &nbsp;&middot;&nbsp; <span style={{color: appliedPatches.length === D.patches.length ? "var(--sage)" : "var(--gold)"}}>{appliedPatches.length}/{D.patches.length} applied</span></div>
      </div>

      <RepairDAG
        patches={visiblePatches}
        appliedPatches={appliedPatches}
        setAppliedPatches={setAppliedPatches}
        setScreen={setScreen}
      />

      <div style={{display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap"}}>
        <button
          className={`btn ${selectedPatch === null ? "" : "ghost"}`}
          onClick={() => setSelectedPatch(null)}
        >ALL</button>
        {D.patches.map(p => (
          <button
            key={p.id}
            className={`btn ${selectedPatch === p.id ? "" : "ghost"}`}
            onClick={() => setSelectedPatch(p.id)}
          >{p.id} · {p.primitive.split(" ")[0]}</button>
        ))}
      </div>

      {visiblePatches.map(p => {
        const v = D.violations.find(v => v.id === p.violation);
        const isApplied = appliedPatches.includes(p.id);
        return (
          <div key={p.id} className="patch-block">
            <div className="patch-head">
              <div className="id">{p.id}</div>
              <div>
                <div className="ctitle">{p.title}</div>
                <div className="muted" style={{fontSize: 11, marginTop: 4}}>fixes <span className="text-brick">{v.id}</span> &nbsp;&middot;&nbsp; {v.type} CONTRACT &nbsp;&middot;&nbsp; failed at step {v.failed_step}</div>
              </div>
              <div className="prim">{p.primitive}</div>
              <div><Pill kind={isApplied ? "pass" : "ok"}>{isApplied ? "APPLIED" : "READY"}</Pill></div>
            </div>
            <div className="diff">
              <div className="pane rem">
                <div className="pane-head">— before &nbsp;&middot;&nbsp; {p.target}</div>
                {p.removed.map((line, i) => (
                  <div key={i} className="line">{line || " "}</div>
                ))}
              </div>
              <div className="pane add">
                <div className="pane-head">+ after &nbsp;&middot;&nbsp; {p.target}</div>
                {p.added.map((line, i) => (
                  <div key={i} className="line">{line || " "}</div>
                ))}
              </div>
            </div>
          </div>
        );
      })}
    </>
  );
}

/* ---------------- REGRESSION ---------------- */
function Regression() {
  const t = D.test;
  return (
    <>
      <div className="section-head">
        <h2>Regression Test &nbsp;//&nbsp; {t.runner}</h2>
        <div className="right">sandbox {t.sandbox_id} &nbsp;&middot;&nbsp; {t.image} &nbsp;&middot;&nbsp; {(t.duration_ms/1000).toFixed(2)}s</div>
      </div>

      <div className="row" style={{alignItems: "stretch", marginBottom: 14}}>
        <div className="card grow">
          <div className="card-head">
            <span>stdout &nbsp;&middot;&nbsp; {t.name}</span>
            <span className="right">live · daytona stream</span>
          </div>
          <div className="term">
            {t.lines.map((l, i) => (
              <div key={i} className="ln">
                <span className="t">{l.t}</span>
                <span className={`k ${l.k}`}>{l.k}</span>
                <span className={`v ${l.k === "pass" ? "pass" : ""}`}>{l.v || "\u00A0"}</span>
              </div>
            ))}
            <div className="ln">
              <span className="t">&gt;_</span>
              <span className="k info">term</span>
              <span className="v"><span className="cursor"></span></span>
            </div>
          </div>
        </div>
        <div className="card" style={{width: 360}}>
          <div className="card-head"><span>Sandbox</span><span className="right">daytona</span></div>
          <div className="kv-list">
            <div className="lbl">ID</div><div className="val">{t.sandbox_id}</div>
            <div className="lbl">Image</div><div className="val">{t.image}</div>
            <div className="lbl">Runner</div><div className="val">pytest 8.2.0</div>
            <div className="lbl">Duration</div><div className="val">{(t.duration_ms/1000).toFixed(2)}s</div>
            <div className="lbl">Status</div><div className="val"><Pill kind="pass">ALL PASS</Pill></div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><span>Assertions</span><span className="right">{t.assertions.length} · {t.assertions.length} passed</span></div>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{width: 60}}>ID</th>
              <th>Assertion</th>
              <th style={{width: 100}}>Time</th>
              <th style={{width: 100}}>Status</th>
            </tr>
          </thead>
          <tbody>
            {t.assertions.map(a => (
              <tr key={a.id}>
                <td className="text-2">{a.id}</td>
                <td><span className="text-gold">{a.name}</span></td>
                <td className="num-col">{a.time_ms} ms</td>
                <td><Pill kind="pass">PASS</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* ---------------- REPORT ---------------- */
function Report({ setScreen }) {
  const r = D.report;
  return (
    <>
      <div className="section-head">
        <h2>Final Report &nbsp;//&nbsp; Contract Violation Report</h2>
        <div className="right">{D.run.id} &nbsp;&middot;&nbsp; ready for export</div>
      </div>

      <div className="report-grid" style={{marginBottom: 14}}>
        <div className="card summary">
          <div className="card-head"><span>Executive Summary</span><span className="right">auto-generated</span></div>
          <div className="card-body" style={{padding: "16px 18px"}}>
            <p>{r.summary}</p>
          </div>
        </div>
        <div className="approval">
          <div className="big">
            <span className="sq"></span>
            <span className="label">{r.approval.status.replace("_", " ")}</span>
          </div>
          <div className="kv-list">
            <div className="lbl">Operator</div><div className="val">{r.approval.operator}</div>
            <div className="lbl">Requested</div><div className="val">{r.approval.requested_at}</div>
            <div className="lbl">SLA</div><div className="val">{r.approval.sla}</div>
            <div className="lbl">Channel</div><div className="val">UserProxyAgent / HumanGate</div>
          </div>
          <hr />
          <div className="btn-row">
            <button className="btn">APPROVE &amp; RERUN</button>
            <button className="btn ghost">REJECT</button>
          </div>
        </div>
      </div>

      <div className="row" style={{alignItems: "stretch"}}>
        <div className="card grow">
          <div className="card-head"><span>Patches Applied</span><span className="right">{r.patches_applied.length} primitives</span></div>
          <div className="card-body" style={{padding: 0}}>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{width: 60}}>ID</th>
                  <th style={{width: 220}}>AG2 Primitive</th>
                  <th>Target</th>
                  <th style={{width: 90}}>Status</th>
                </tr>
              </thead>
              <tbody>
                {D.patches.map(p => (
                  <tr key={p.id}>
                    <td className="text-2">{p.id}</td>
                    <td className="text-gold" style={{letterSpacing: "0.12em", fontSize: 11.5}}>{p.primitive}</td>
                    <td>{p.target}</td>
                    <td><Pill kind="pass">APPLIED</Pill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card" style={{width: 360}}>
          <div className="card-head"><span>Verification</span><span className="right">daytona</span></div>
          <div className="kv-list">
            <div className="lbl">Test</div><div className="val">{D.test.name}</div>
            <div className="lbl">Assertions</div><div className="val">4 / 4 passed</div>
            <div className="lbl">Sandbox</div><div className="val">{D.test.sandbox_id}</div>
            <div className="lbl">Duration</div><div className="val">{(D.test.duration_ms/1000).toFixed(2)}s</div>
          </div>
          <hr />
          <div className="btn-row">
            <button className="btn ghost" onClick={() => setScreen("regression")}>VIEW TEST</button>
            <button className="btn ghost">EXPORT JSON</button>
          </div>
        </div>
      </div>

      <div style={{marginTop: 22, color: "var(--text-3)", fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", borderTop: "1px solid var(--border)", paddingTop: 14, display: "flex", justifyContent: "space-between"}}>
        <span>concord-lite &nbsp;&middot;&nbsp; report v1 &nbsp;&middot;&nbsp; {D.run.id}</span>
        <span>workflow under test &nbsp;→&nbsp; contract violation &nbsp;→&nbsp; repair &nbsp;→&nbsp; regression test</span>
      </div>
    </>
  );
}

/* ---------------- APP ---------------- */
function App() {
  const [screen, setScreen] = useState("overview");
  const [selectedPatch, setSelectedPatch] = useState(null);
  const [appliedPatches, setAppliedPatches] = useState([]);
  const [data, setData] = useState(FIXTURE_DATA);
  const [sourceMode, setSourceMode] = useState("fixture");
  const [connectionState, setConnectionState] = useState("idle");
  const [liveStatus, setLiveStatus] = useState(FIXTURE_DATA.status || "completed");
  const [tenantUsage, setTenantUsage] = useState(null);
  D = data;

  // when leaving repair screen, clear filter
  useEffect(() => { if (screen !== "repair") setSelectedPatch(null); }, [screen]);

  useEffect(() => {
    if (sourceMode === "fixture") {
      setConnectionState("idle");
      setLiveStatus(FIXTURE_DATA.status || "completed");
      setData(FIXTURE_DATA);
      setTenantUsage(null);
      return;
    }

    const liveRunId = new URLSearchParams(window.location.search).get("run") || window.CONCORD_RUN_ID || FIXTURE_DATA.run.id;
    const headers = liveHeaders();
    let cancelled = false;
    let eventSource = null;
    let terminalSeen = false;
    let lastSequence = 0;
    let reconnectTimer = null;

    async function refreshRun() {
      const response = await fetch(`/api/runs/${liveRunId}`, { headers });
      if (!response.ok) throw new Error(`run fetch failed: ${response.status}`);
      const liveData = await response.json();
      if (cancelled) return;
      setData(normalizeDashboardData(liveData, { fallbackFixture: false }));
      setLiveStatus(liveData.status || "loaded");
      try {
        const usageResponse = await fetch("/api/tenant/usage", { headers });
        if (usageResponse.ok && !cancelled) setTenantUsage(await usageResponse.json());
      } catch (_error) {
        if (!cancelled) setTenantUsage(null);
      }
    }

    async function openLiveRun() {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      setConnectionState("connecting");
      try {
        await refreshRun();
        if (cancelled) return;
        const streamToken = await openStreamToken(liveRunId, headers);
        if (cancelled) return;
        eventSource = new EventSource(`/api/runs/${liveRunId}/events?stream_token=${encodeURIComponent(streamToken)}`);
        eventSource.addEventListener("run.status", async (event) => {
          const payload = JSON.parse(event.data);
          const sequence = Number(payload.sequence || event.lastEventId || 0);
          if (sequence && sequence <= lastSequence) return;
          if (sequence) lastSequence = sequence;
          if (cancelled) return;
          setConnectionState("connected");
          setLiveStatus(payload.status);
          if (payload.terminal) {
            terminalSeen = true;
            eventSource.close();
            await refreshRun();
            if (!cancelled) setConnectionState("connected");
          }
        });
        eventSource.onopen = () => {
          if (!cancelled) setConnectionState("connected");
        };
        eventSource.onerror = () => {
          if (terminalSeen) return;
          if (!cancelled) {
            setConnectionState("connecting");
            reconnectTimer = setTimeout(openLiveRun, 1000);
          }
        };
      } catch (error) {
        if (!cancelled) {
          setConnectionState("error");
          setLiveStatus("unavailable");
        }
      }
    }

    openLiveRun();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (eventSource) eventSource.close();
    };
  }, [sourceMode]);

  return (
    <div className="shell" data-screen-label={SCREENS.find(s=>s.id===screen).num + " " + SCREENS.find(s=>s.id===screen).label}>
      <TopBar
        screen={screen}
        setScreen={setScreen}
        sourceMode={sourceMode}
        setSourceMode={setSourceMode}
        connectionState={connectionState}
        liveStatus={liveStatus}
      />
      <MetaStrip sourceMode={sourceMode} connectionState={connectionState} />
      <main className="main">
        {screen === "overview"   && <Overview setScreen={setScreen} tenantUsage={tenantUsage} />}
        {screen === "topology"   && <Topology setScreen={setScreen} setSelectedPatch={setSelectedPatch} />}
        {screen === "trace"      && <Trace />}
        {screen === "violations" && <Violations setScreen={setScreen} setSelectedPatch={setSelectedPatch} />}
        {screen === "repair"     && <Repair selectedPatch={selectedPatch} setSelectedPatch={setSelectedPatch} appliedPatches={appliedPatches} setAppliedPatches={setAppliedPatches} setScreen={setScreen} />}
        {screen === "regression" && <Regression />}
        {screen === "report"     && <Report setScreen={setScreen} />}
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

