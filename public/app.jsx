/* global React, ReactDOM */
const { useState, useEffect, useMemo } = React;
const BOOT_DATA = window.CONCORD_DATA;
const SESSION_AUTH_KEY = "concord.session_auth";
let BROWSER_AUTH = readSessionAuth();
applyBrowserAuth(BROWSER_AUTH);

function readSessionAuth() {
  if (typeof window === "undefined" || !window.sessionStorage) return {};
  try {
    const raw = window.sessionStorage.getItem(SESSION_AUTH_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || !parsed.api_key) return {};
    return {
      api_key: String(parsed.api_key),
      tenant_id: String(parsed.tenant_id || "local"),
      name: String(parsed.name || ""),
      key_prefix: String(parsed.key_prefix || ""),
    };
  } catch (_error) {
    return {};
  }
}

function applyBrowserAuth(auth) {
  if (typeof window === "undefined" || !auth?.api_key) return;
  BROWSER_AUTH = {
    api_key: String(auth.api_key),
    tenant_id: String(auth.tenant_id || "local"),
    name: String(auth.name || ""),
    key_prefix: String(auth.key_prefix || ""),
  };
  if (window.sessionStorage) {
    window.sessionStorage.setItem(SESSION_AUTH_KEY, JSON.stringify(BROWSER_AUTH));
  }
}

function clearBrowserAuth() {
  BROWSER_AUTH = {};
  if (typeof window === "undefined") return;
  if (window.sessionStorage) window.sessionStorage.removeItem(SESSION_AUTH_KEY);
  delete window.CONCORD_API_KEY;
  delete window.CONCORD_TENANT_ID;
}

function currentBrowserAuth() {
  const apiKey = BROWSER_AUTH.api_key || window.CONCORD_API_KEY || "";
  return {
    has_key: Boolean(apiKey),
    tenant_id: BROWSER_AUTH.tenant_id || window.CONCORD_TENANT_ID || "",
    key_prefix: BROWSER_AUTH.key_prefix || (apiKey ? `${apiKey.slice(0, 11)}...` : ""),
    name: BROWSER_AUTH.name || "",
  };
}

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
  const tenantId = BROWSER_AUTH.tenant_id || window.CONCORD_TENANT_ID;
  const apiKey = BROWSER_AUTH.api_key || window.CONCORD_API_KEY;
  if (tenantId) headers["X-Tenant-ID"] = tenantId;
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
    headers["X-Concord-API-Key"] = apiKey;
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

function buildReportExportPayload(data) {
  const source = data || {};
  const report = source.report || {};
  const test = source.test || {};
  const cost = source.cost || report.cost_summary || {};
  return {
    exported_at: new Date().toISOString(),
    run: source.run || {},
    status: source.status || "",
    workflow: {
      name: source.run?.workflow || source.workflow_name || "",
      topology: source.topology || {},
      contracts: source.contracts || [],
      routes: source.routes || [],
      recurrences: source.recurrences || [],
    },
    verdicts: {
      violation_count: report.violation_count ?? source.violations?.length ?? 0,
      severity_summary: report.severity_summary || source.stats?.severity || {},
      regression_test_status: report.regression_test_status || test.status || "",
      validation_state: report.validation_state || test.validation_state || "",
      approval_status: report.approval?.status || "",
    },
    evidence: {
      trace: source.trace || [],
      spans: source.spans || [],
      violations: source.violations || [],
    },
    patches: source.patches || report.patches || [],
    regression: {
      test,
      regression_tests: report.regression_tests || [],
      regression_summary: report.regression_summary || {},
      validation_state: report.validation_state || test.validation_state || "",
      validation_summary: report.validation_summary || {},
      generated_test_status: report.generated_test_status || test.generated_test_status || "",
      fallback_used: report.fallback_used ?? test.fallback_used ?? false,
      fallback_reason: report.fallback_reason || test.fallback_reason || "",
      sandbox_id: report.sandbox_id || test.sandbox_id || "",
      duration_ms: report.regression_duration_ms ?? test.duration_ms ?? 0,
    },
    cost,
    report,
  };
}

function reportExportFilename(data) {
  const runId = data?.run?.id || data?.run_id || "run";
  const safeRunId = String(runId).replace(/[^A-Za-z0-9._-]+/g, "-");
  return `concord-report-${safeRunId}.json`;
}

function downloadReportJson(filename, jsonText) {
  const blob = new Blob([jsonText], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

async function writeClipboardText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  return copied;
}

async function exportReportJson(data) {
  const payload = buildReportExportPayload(data);
  const jsonText = JSON.stringify(payload, null, 2);
  const filename = reportExportFilename(data);
  downloadReportJson(filename, jsonText);
  let copied = false;
  try {
    copied = await writeClipboardText(jsonText);
  } catch (_error) {
    copied = false;
  }
  return { payload, jsonText, filename, copied };
}

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

function normalizedStatus(value, fallback = "UNKNOWN") {
  return String(value || fallback).trim().toUpperCase();
}

function statusPillKind(status) {
  const normalized = normalizedStatus(status).replaceAll("-", "_");
  if (["PASS", "PASSED", "SUCCESS", "APPLIED"].includes(normalized)) return "pass";
  if (["FAIL", "FAILED", "ERROR", "CREDENTIAL_FAILURE", "EXECUTION_ERROR"].includes(normalized)) return "fail";
  return "warn";
}

function canonicalValidationState(value, fallback = "unavailable") {
  const normalized = String(value || fallback).trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  if (["pass", "passed", "success"].includes(normalized)) return "passed";
  if (["fail", "failed"].includes(normalized)) return "failed";
  if (["skipped", "unavailable", "credential_failure", "execution_error"].includes(normalized)) return normalized;
  if (normalized === "error") return "execution_error";
  return "unavailable";
}

function validationLabel(state) {
  return {
    passed: "PASSED",
    failed: "FAILED",
    skipped: "SKIPPED",
    unavailable: "UNAVAILABLE",
    credential_failure: "CREDENTIAL FAILURE",
    execution_error: "EXECUTION ERROR",
  }[canonicalValidationState(state)] || "UNAVAILABLE";
}

function validationPillKind(state) {
  const normalized = canonicalValidationState(state);
  if (normalized === "passed") return "pass";
  if (["failed", "credential_failure", "execution_error"].includes(normalized)) return "fail";
  return "warn";
}

function testAssertionStats(test = D.test) {
  const assertions = Array.isArray(test?.assertions) ? test.assertions : [];
  const counts = assertions.reduce((acc, assertion) => {
    const status = normalizedStatus(assertion.status);
    if (status === "PASS" || status === "PASSED") acc.pass += 1;
    else if (status === "FAIL" || status === "FAILED") acc.fail += 1;
    else if (status === "ERROR") acc.error += 1;
    else acc.other += 1;
    return acc;
  }, { pass: 0, fail: 0, error: 0, other: 0 });
  const total = assertions.length;
  let status = canonicalValidationState(
    test?.validation_state || D.report?.validation_state,
    test?.status || D.report?.regression_test_status || (total ? "unknown" : "unavailable"),
  );
  if (total > 0) {
    if (test?.validation_state || D.report?.validation_state) {
      status = canonicalValidationState(test?.validation_state || D.report?.validation_state);
    } else if (counts.fail > 0) status = "failed";
    else if (counts.error > 0) status = "execution_error";
    else if (counts.other > 0 || counts.pass < total) status = "unavailable";
    else status = "passed";
  }
  return { ...counts, total, status, label: validationLabel(status) };
}

function assertionRepairLink(assertion, index) {
  const numericId = Number(String(assertion?.id || "").replace(/\D/g, ""));
  const patch = assertion?.patch_id
    ? D.patches.find((item) => item.id === assertion.patch_id)
    : D.patches[numericId > 0 ? numericId - 1 : index];
  const violation = assertion?.violation_id
    ? D.violations.find((item) => item.id === assertion.violation_id)
    : patch ? D.violations.find((item) => item.id === patch.violation) : null;
  return { patch, violation };
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
        <div className="mark">CONCORD</div>
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

function formatRunStarted(value) {
  if (!value) return "start unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toISOString().replace("T", " ").replace("Z", " UTC");
}

function severitySummary(violations = D.violations) {
  return (violations || []).reduce((acc, violation) => {
    const key = normalizedStatus(violation.severity, "LOW").toLowerCase();
    if (key === "high") acc.high += 1;
    else if (key === "med" || key === "medium") acc.medium += 1;
    else acc.low += 1;
    return acc;
  }, { high: 0, medium: 0, low: 0 });
}

function latestTraceContextValue(keys, fallback = 0) {
  const keyList = Array.isArray(keys) ? keys : [keys];
  for (const event of [...(D.trace || [])].reverse()) {
    const ctx = event.ctx || {};
    for (const key of keyList) {
      if (Object.prototype.hasOwnProperty.call(ctx, key)) {
        const value = ctx[key];
        if (Array.isArray(value)) return value.length;
        return value ?? fallback;
      }
    }
  }
  return fallback;
}

function handoffCount() {
  return (D.trace || []).filter((event) =>
    String(event.type || "").toLowerCase() === "handoff" ||
    Object.prototype.hasOwnProperty.call(event.ctx || {}, "handoff_to")
  ).length;
}

function approvalState() {
  const traceValue = latestTraceContextValue("approval_status", "");
  const reportValue = D.report?.approval?.status || "";
  return normalizedStatus(traceValue || reportValue || "unknown").replaceAll("_", " ");
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
  const severity = severitySummary();
  const patchCount = D.patches.length || D.stats.repair_ready || 0;
  const retrievedSources = latestTraceContextValue(["retrieved_sources", "retrieved_sources_count"], 0);
  const verifiedSources = latestTraceContextValue(["verified_sources_count", "verified"], 0);
  const approval = approvalState();
  const runState = normalizedStatus(D.status || D.run.final_output_status || "unknown").replaceAll("_", " ");
  return (
    <>
      <div className="section-head">
        <h2>Run Summary &nbsp;//&nbsp; {D.run.id} &nbsp;&middot;&nbsp; {D.run.workflow}</h2>
        <div className="right">started {formatRunStarted(D.run.started)} &nbsp;&middot;&nbsp; {runState}</div>
      </div>

      <div className="stat-grid" style={{marginBottom: 22}}>
        <div className="stat">
          <div className="stat-accent brick"></div>
          <div className="lbl">Contract Violations</div>
          <div className="num brick">{D.stats.violations}</div>
          <div className="delta">{severity.high} HIGH &nbsp;/&nbsp; {severity.medium} MED &nbsp;/&nbsp; {severity.low} LOW</div>
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
          <div className="delta">AG2 primitives mapped &nbsp;&middot;&nbsp; {patchCount} patch{patchCount === 1 ? "" : "es"}</div>
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
              <div><div className="muted" style={{fontSize: 10, letterSpacing: "0.14em"}}>RETRIEVED</div><div>{retrievedSources} source{retrievedSources === 1 ? "" : "s"}</div></div>
              <div><div className="muted" style={{fontSize: 10, letterSpacing: "0.14em"}}>VERIFIED</div><div className={Number(verifiedSources) > 0 ? "text-sage" : "text-brick"}>{verifiedSources} source{verifiedSources === 1 ? "" : "s"}</div></div>
              <div><div className="muted" style={{fontSize: 10, letterSpacing: "0.14em"}}>HANDOFFS</div><div>{handoffCount()}</div></div>
              <div><div className="muted" style={{fontSize: 10, letterSpacing: "0.14em"}}>APPROVAL</div><div className={approval === "APPROVED" ? "text-sage" : "text-brick"}>{approval}</div></div>
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
  const toolEventCount = D.trace.filter((event) => String(event.type || "").toLowerCase().includes("tool")).length;
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
        <div className="right">{D.trace.length} events &nbsp;&middot;&nbsp; {toolEventCount} tool events &nbsp;&middot;&nbsp; {D.violations.length} violations</div>
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
function regressionForViolation(violation, patch) {
  const reportTests = D.report?.regression_tests || [];
  const byContract = reportTests.find((test) =>
    String(test.contract_type || "").toUpperCase() === String(violation.type || "").toUpperCase()
  );
  const patchNumber = Number(String(patch?.id || "").replace(/\D/g, ""));
  const assertionId = Number.isFinite(patchNumber) && patchNumber > 0 ? `A${patchNumber}` : "";
  const assertion = (D.test?.assertions || []).find((item) =>
    item.violation_id === violation.id ||
    (patch && item.patch_id === patch.id) ||
    item.id === assertionId
  );
  const status = byContract?.test_status || assertion?.status || D.report?.regression_test_status || "unknown";
  const state = canonicalValidationState(
    byContract?.validation_state || assertion?.validation_state || D.report?.validation_state,
    status,
  );
  return {
    status: validationLabel(state),
    state,
    label: byContract?.test_name || byContract?.assertion || assertion?.name || "regression pending",
  };
}

function regressionPillKind(status) {
  return validationPillKind(status);
}

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
        <div className="right">evidence → primitive → patch → regression</div>
      </div>

      <div className="viol-list" style={{marginBottom: 14}}>
        <div className="viol-row" style={{background: "var(--bg)", cursor: "default"}}>
          <div className="sev-bar" style={{background: "var(--border-2)"}}></div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Severity</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Contract</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Title</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Expected / Observed</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Failed Agent · Step</div>
          <div className="muted" style={{letterSpacing: "0.16em", fontSize: 10, textTransform: "uppercase"}}>Repair Path</div>
        </div>
        {D.violations.map(v => {
          const patch = D.patches.find(p => p.violation === v.id);
          const regression = regressionForViolation(v, patch);
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
              <div className="repair-path">
                <div>
                  <span className="path-label">Evidence</span>
                  <span>{v.evidence?.[0] || v.observed}</span>
                </div>
                <div>
                  <span className="path-label">AG2 primitive</span>
                  <span className="text-gold">{patch ? patch.primitive : "unmapped"}</span>
                </div>
                <div>
                  <span className="path-label">Patch</span>
                  {patch ? (
                    <button
                      type="button"
                      className="inline-action"
                      onClick={(event) => {
                        event.stopPropagation();
                        onClick(v);
                      }}
                    >
                      VIEW PATCH {patch.id}
                    </button>
                  ) : (
                    <span>—</span>
                  )}
                </div>
                <div>
                  <span className="path-label">Regression</span>
                  <Pill kind={regressionPillKind(regression.state)}>{regression.status}</Pill>
                  <span className="muted path-test">{regression.label}</span>
                </div>
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
            <div className="sub">{patches.length} AG2 primitives inserted · ready for regression</div>
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
  const stats = testAssertionStats(t);
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
            <div className="lbl">Runner</div><div className="val">{t.runner || "unknown"}</div>
            <div className="lbl">Duration</div><div className="val">{(t.duration_ms/1000).toFixed(2)}s</div>
            <div className="lbl">Validation</div><div className="val"><Pill kind={validationPillKind(stats.status)}>{stats.label}</Pill></div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><span>Assertions</span><span className="right">{stats.pass} pass · {stats.fail} fail · {stats.error} error</span></div>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{width: 60}}>ID</th>
              <th>Assertion</th>
              <th style={{width: 220}}>Repair Link</th>
              <th style={{width: 100}}>Time</th>
              <th style={{width: 100}}>Status</th>
            </tr>
          </thead>
          <tbody>
            {t.assertions.map((a, index) => {
              const link = assertionRepairLink(a, index);
              return (
                <tr key={a.id}>
                  <td className="text-2">{a.id}</td>
                  <td><span className="text-gold">{a.name}</span></td>
                  <td>
                    {link.patch && link.violation ? (
                      <span className="muted">fixes <span className="text-brick">{link.violation.id}</span> · {link.patch.id} · {link.patch.primitive}</span>
                    ) : (
                      <span className="muted">unmapped</span>
                    )}
                  </td>
                  <td className="num-col">{a.time_ms} ms</td>
                  <td>
                    {(() => {
                      const state = canonicalValidationState(a.validation_state, a.status);
                      return <Pill kind={validationPillKind(state)}>{validationLabel(state)}</Pill>;
                    })()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* ---------------- REPORT ---------------- */
function Report({ setScreen }) {
  const r = D.report;
  const [exportState, setExportState] = useState("idle");
  const stats = testAssertionStats(D.test);
  const appliedPatchIds = new Set((r.patches_applied || []).map((entry) => String(entry).trim().split(/\s+/)[0]));
  async function handleExport() {
    setExportState("exporting");
    try {
      const result = await exportReportJson(D);
      setExportState(result.copied ? "copied" : "downloaded");
      setTimeout(() => setExportState("idle"), 2400);
    } catch (_error) {
      setExportState("error");
    }
  }
  const exportLabel = {
    idle: "EXPORT JSON",
    exporting: "EXPORTING...",
    copied: "EXPORTED + COPIED",
    downloaded: "DOWNLOADED",
    error: "EXPORT FAILED",
  }[exportState];
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
          <div className="card-head"><span>Patches Applied</span><span className="right">{appliedPatchIds.size} / {D.patches.length} primitives</span></div>
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
                {D.patches.map(p => {
                  const isApplied = appliedPatchIds.has(p.id);
                  return (
                    <tr key={p.id}>
                      <td className="text-2">{p.id}</td>
                      <td className="text-gold" style={{letterSpacing: "0.12em", fontSize: 11.5}}>{p.primitive}</td>
                      <td>{p.target}</td>
                      <td><Pill kind={isApplied ? "pass" : "warn"}>{isApplied ? "APPLIED" : "PENDING"}</Pill></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card" style={{width: 360}}>
          <div className="card-head"><span>Verification</span><span className="right">daytona</span></div>
          <div className="kv-list">
            <div className="lbl">Test</div><div className="val">{D.test.name}</div>
            <div className="lbl">Assertions</div><div className="val">{stats.pass} / {stats.total} passed</div>
            <div className="lbl">Validation</div><div className="val"><Pill kind={validationPillKind(stats.status)}>{stats.label}</Pill></div>
            <div className="lbl">Sandbox</div><div className="val">{D.test.sandbox_id}</div>
            <div className="lbl">Duration</div><div className="val">{(D.test.duration_ms/1000).toFixed(2)}s</div>
          </div>
          <hr />
          <div className="btn-row">
            <button className="btn ghost" onClick={() => setScreen("regression")}>VIEW TEST</button>
            <button className="btn ghost" onClick={handleExport} disabled={exportState === "exporting"}>
              {exportLabel}
            </button>
          </div>
          {exportState !== "idle" && (
            <div className="text-2" aria-live="polite" style={{fontSize: 10.5, letterSpacing: "0.12em", padding: "8px 12px 0"}}>
              {exportState === "copied" && "JSON downloaded and copied to clipboard"}
              {exportState === "downloaded" && "JSON downloaded; clipboard unavailable"}
              {exportState === "exporting" && "Preparing report payload"}
              {exportState === "error" && "Export failed in this browser"}
            </div>
          )}
        </div>
      </div>

      <div style={{marginTop: 22, color: "var(--text-3)", fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", borderTop: "1px solid var(--border)", paddingTop: 14, display: "flex", justifyContent: "space-between"}}>
        <span>concord &nbsp;&middot;&nbsp; report v1 &nbsp;&middot;&nbsp; {D.run.id}</span>
        <span>workflow under test &nbsp;→&nbsp; contract violation &nbsp;→&nbsp; repair &nbsp;→&nbsp; regression test</span>
      </div>
    </>
  );
}

/* ---------------- APP ---------------- */
/* ---------------- SubmitForm (Phase 2) ----------------
   Landing page for the new product flow. Live runs are submitted from
   here; fixture mode is reachable via the legacy "?fixture=1" param or
   the sidebar control. */
const TASK_MAX = 1000;
const RESEARCH_QUESTION_MAX = 500;
const WORKFLOW_IMPORT_MAX = 6000;

function hasBrowserTenantCredentials() {
  return Boolean(BROWSER_AUTH.api_key || window.CONCORD_API_KEY);
}

async function fetchApiKeyStatus() {
  const response = await fetch("/api/api-keys/status", { headers: liveHeaders() });
  if (!response.ok) return null;
  return response.json();
}

function statusBlocksProtectedFetch(status) {
  return Boolean(status && !status.authenticated && (status.requires_api_key || status.can_create_first_key === false));
}

async function submitRunPayload(payload) {
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  if (!hasBrowserTenantCredentials()) {
    const publicResponse = await fetch("/api/public/runs", options);
    if (publicResponse.ok || ![403, 404].includes(publicResponse.status)) {
      return publicResponse;
    }
  }
  return fetch("/api/runs", {
    ...options,
    headers: { ...options.headers, ...liveHeaders() },
  });
}

async function postWorkflowImportPayload(payload) {
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  if (!hasBrowserTenantCredentials()) {
    const publicResponse = await fetch("/api/public/workflows", options);
    if (publicResponse.ok || ![403, 404].includes(publicResponse.status)) {
      return publicResponse;
    }
  }
  return fetch("/api/workflows", {
    ...options,
    headers: { ...options.headers, ...liveHeaders() },
  });
}

function apiDetailText(detail) {
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || JSON.stringify(item)).join("; ");
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return String(detail || "Request failed");
}

function importWorkflowPayload(specText, workflowName) {
  const spec = specText.trim();
  const name = workflowName.trim();
  if (!spec) throw new Error("Import spec is required.");
  if (spec.startsWith("{") || spec.startsWith("[")) {
    let payload;
    try {
      payload = JSON.parse(spec);
    } catch (error) {
      throw new Error(`Invalid JSON: ${error.message}`);
    }
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("JSON workflow spec must be an object.");
    }
    const normalized = { ...payload };
    if (!normalized.name && name) normalized.name = name;
    if (!normalized.name) throw new Error("Workflow name is required.");
    if (typeof normalized.name !== "string") throw new Error("Workflow name must be a string.");
    if (
      normalized.declared_topology !== undefined &&
      (typeof normalized.declared_topology !== "object" || Array.isArray(normalized.declared_topology))
    ) {
      throw new Error("declared_topology must be an object.");
    }
    for (const key of ["agents", "tools", "contracts"]) {
      if (normalized[key] !== undefined && !Array.isArray(normalized[key])) {
        throw new Error(`${key} must be an array.`);
      }
    }
    if (!normalized.declared_topology) normalized.declared_topology = {};
    if (normalized.agents === undefined) normalized.agents = [];
    if (normalized.tools === undefined) normalized.tools = [];
    if (normalized.contracts === undefined) normalized.contracts = [];
    return normalized;
  }
  if (!name) throw new Error("Workflow name is required for YAML imports.");
  return {
    name,
    owner: "",
    declared_topology: {},
    agents: [],
    tools: [],
    contracts: [],
    contracts_yaml: spec,
  };
}

function SubmitForm({ onSubmitted, onSwitchToFixture }) {
  const [workflows, setWorkflows] = useState([]);
  const [workflowsState, setWorkflowsState] = useState("loading");
  const [workflowsError, setWorkflowsError] = useState("");
  const [workflowId, setWorkflowId] = useState("");
  const [task, setTask] = useState("");
  const [researchQuestion, setResearchQuestion] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [importName, setImportName] = useState("");
  const [importSpec, setImportSpec] = useState("");
  const [importState, setImportState] = useState("idle");
  const [importError, setImportError] = useState("");
  const [importSuccess, setImportSuccess] = useState("");
  const [apiKeyOpen, setApiKeyOpen] = useState(false);
  const [apiTenantId, setApiTenantId] = useState(() => currentBrowserAuth().tenant_id || "local");
  const [apiKeyName, setApiKeyName] = useState("Browser session");
  const [apiKeyState, setApiKeyState] = useState("idle");
  const [apiKeyError, setApiKeyError] = useState("");
  const [apiKeySuccess, setApiKeySuccess] = useState("");
  const [createdApiKey, setCreatedApiKey] = useState("");
  const [existingApiKey, setExistingApiKey] = useState("");
  const [existingKeyState, setExistingKeyState] = useState("idle");
  const [canCreateApiKey, setCanCreateApiKey] = useState(() => currentBrowserAuth().has_key);
  const [copyState, setCopyState] = useState("idle");
  const [authInfo, setAuthInfo] = useState(() => currentBrowserAuth());
  const [authVersion, setAuthVersion] = useState(0);
  const [submitState, setSubmitState] = useState("idle");
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const hadCredentials = hasBrowserTenantCredentials();
        const status = await fetchApiKeyStatus();
        if (status) {
          const allowedToCreate = Boolean(status.authenticated || (!status.requires_api_key && status.can_create_first_key));
          setCanCreateApiKey(allowedToCreate);
          if (hadCredentials && status.requires_api_key && !status.authenticated) {
            clearBrowserAuth();
            setAuthInfo(currentBrowserAuth());
            setApiKeyOpen(true);
            throw new Error("invalid API key");
          }
          if (!hadCredentials && statusBlocksProtectedFetch(status)) {
            setApiKeyOpen(true);
            throw new Error(status.requires_api_key ? "missing API key" : "first API key must be created from localhost or deployment shell");
          }
        }
        const res = await fetch("/api/workflows", { headers: liveHeaders() });
        if (!res.ok) throw new Error(`workflows fetch ${res.status}`);
        const body = await res.json();
        const list = Array.isArray(body) ? body : (body.workflows || []);
        if (!cancelled) {
          setWorkflows(list);
          setWorkflowId(list[0]?.workflow_id || list[0]?.id || "");
          setWorkflowsState("loaded");
        }
      } catch (err) {
        if (!cancelled) {
          setWorkflowsError(String(err.message || err));
          setWorkflowsState("error");
        }
      }
    }
    load();
    return () => { cancelled = true; };
  }, [authVersion]);

  const workflowAuthError =
    workflowsState === "error" && /401|403|missing api key|invalid api key/i.test(workflowsError);

  useEffect(() => {
    if (workflowAuthError) setApiKeyOpen(true);
  }, [workflowAuthError]);

  const canSubmit =
    workflowId &&
    task.trim() &&
    researchQuestion.trim() &&
    task.length <= TASK_MAX &&
    researchQuestion.length <= RESEARCH_QUESTION_MAX &&
    submitState !== "submitting";

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitState("submitting");
    setSubmitError("");
    try {
      const res = await submitRunPayload({
        workflow_id: workflowId,
        task_spec: { task: task.trim(), research_question: researchQuestion.trim(), mode: "live" },
      });
      if (res.status === 422 || res.status === 400) {
        const body = await res.json().catch(() => ({}));
        setSubmitError(`Validation error: ${body.detail || res.statusText}`);
        setSubmitState("error");
        return;
      }
      if (res.status === 404) {
        setSubmitError(`Workflow ${workflowId} not found.`);
        setSubmitState("error");
        return;
      }
      if (!res.ok) {
        setSubmitError(`Server error ${res.status}.`);
        setSubmitState("error");
        return;
      }
      const body = await res.json();
      setSubmitState("idle");
      if (onSubmitted) onSubmitted(body.run_id);
    } catch (err) {
      setSubmitError(`Network error: ${err.message || err}`);
      setSubmitState("error");
    }
  }

  async function handleImportWorkflow() {
    setImportState("submitting");
    setImportError("");
    setImportSuccess("");
    try {
      const payload = importWorkflowPayload(importSpec, importName);
      const res = await postWorkflowImportPayload(payload);
      const body = await res.json().catch(() => ({}));
      if (res.status === 400 || res.status === 422) {
        setImportError(`Validation error: ${apiDetailText(body.detail || res.statusText)}`);
        setImportState("error");
        return;
      }
      if (!res.ok) {
        setImportError(`Server error ${res.status}.`);
        setImportState("error");
        return;
      }
      const created = body.workflow_id ? body : { ...body, workflow_id: body.id };
      setWorkflows((current) => {
        const withoutDuplicate = current.filter(
          (workflow) => (workflow.workflow_id || workflow.id) !== created.workflow_id
        );
        return [created, ...withoutDuplicate];
      });
      setWorkflowId(created.workflow_id || created.id);
      setWorkflowsState("loaded");
      setImportSuccess(`Imported ${created.name || created.workflow_id || "workflow"}.`);
      setImportState("success");
    } catch (err) {
      setImportError(`Validation error: ${err.message || err}`);
      setImportState("error");
    }
  }

  async function handleCreateApiKey() {
    setApiKeyState("creating");
    setApiKeyError("");
    setApiKeySuccess("");
    setCreatedApiKey("");
    setCopyState("idle");
    try {
      const res = await fetch("/api/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...liveHeaders() },
        body: JSON.stringify({
          tenant_id: apiTenantId.trim() || "local",
          name: apiKeyName.trim() || "Browser session",
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setApiKeyError(`Key creation failed: ${apiDetailText(body.detail || res.statusText)}`);
        setApiKeyState("error");
        return;
      }
      applyBrowserAuth(body);
      setAuthInfo(currentBrowserAuth());
      setApiTenantId(body.tenant_id || apiTenantId);
      setCreatedApiKey(body.api_key || "");
      setApiKeySuccess(`Created key ${body.key_prefix || ""} for ${body.tenant_id || "local"}.`);
      setApiKeyState("success");
      setCanCreateApiKey(true);
      setWorkflowsState("loading");
      setWorkflowsError("");
      setAuthVersion((version) => version + 1);
    } catch (err) {
      setApiKeyError(`Network error: ${err.message || err}`);
      setApiKeyState("error");
    }
  }

  async function handleUseExistingApiKey() {
    const candidate = existingApiKey.trim();
    if (!candidate) return;
    const tenantId = apiTenantId.trim() || "local";
    setExistingKeyState("verifying");
    setApiKeyError("");
    setApiKeySuccess("");
    setCreatedApiKey("");
    try {
      const headers = {
        "Authorization": `Bearer ${candidate}`,
        "X-Concord-API-Key": candidate,
        "X-Tenant-ID": tenantId,
      };
      const res = await fetch("/api/workflows", { headers });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setApiKeyError(`Existing key failed: ${apiDetailText(body.detail || res.statusText)}`);
        setExistingKeyState("error");
        return;
      }
      applyBrowserAuth({
        api_key: candidate,
        tenant_id: tenantId,
        name: "Browser session",
        key_prefix: `${candidate.slice(0, 12)}...`,
      });
      setAuthInfo(currentBrowserAuth());
      setExistingApiKey("");
      setApiKeySuccess(`Loaded session key for ${tenantId}.`);
      setExistingKeyState("success");
      setCanCreateApiKey(true);
      setWorkflowsState("loading");
      setWorkflowsError("");
      setAuthVersion((version) => version + 1);
    } catch (err) {
      setApiKeyError(`Network error: ${err.message || err}`);
      setExistingKeyState("error");
    }
  }

  async function handleCopyApiKey() {
    if (!createdApiKey || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(createdApiKey);
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 1800);
    } catch (_error) {
      setCopyState("error");
    }
  }

  return (
    <div className="landing">
      <div className="landing-card">
        <header className="landing-head">
          <h1 className="landing-mark">CONCORD</h1>
          <p className="landing-sub">
            Submit a research task. Watch the AG2 swarm work it. Concord catches contract violations and proposes repairs in real time.
          </p>
        </header>

        <form className="submit-form" onSubmit={handleSubmit} aria-label="Submit run">
          <div className="form-row">
            <label htmlFor="workflow-picker" className="form-label">Workflow</label>
            {workflowsState === "loading" && <div className="form-loading" role="status">Loading workflows…</div>}
            {workflowsState === "error" && (
              <div className="form-error" role="alert">Could not load workflows: {workflowsError}</div>
            )}
            {workflowsState === "loaded" && workflows.length === 0 && (
              <div className="form-empty">
                No workflows registered yet. Register one via{" "}
                <code>POST /api/workflows</code> first.
              </div>
            )}
            {workflowsState === "loaded" && workflows.length > 0 && (
              <select
                id="workflow-picker"
                className="form-select"
                value={workflowId}
                onChange={(e) => setWorkflowId(e.target.value)}
                aria-required="true"
              >
                {workflows.map((wf) => (
                  <option key={wf.workflow_id || wf.id} value={wf.workflow_id || wf.id}>
                    {wf.name || wf.workflow_id || wf.id}
                  </option>
                ))}
              </select>
            )}
            <div className="api-key-panel">
              <div className="api-key-row">
                <div>
                  <div className="api-key-title">API Access</div>
                  <div className="api-key-meta">
                    {authInfo.has_key
                      ? `${authInfo.tenant_id || "local"} · ${authInfo.key_prefix || "session key"}`
                      : "No session key"}
                  </div>
                </div>
                <div className="api-key-actions">
                  <span className={`api-key-status ${authInfo.has_key ? "ready" : "missing"}`}>
                    {authInfo.has_key ? "READY" : "MISSING"}
                  </span>
                  <button
                    type="button"
                    className="btn-link"
                    onClick={() => setApiKeyOpen((open) => !open)}
                    aria-expanded={apiKeyOpen}
                  >
                    {authInfo.has_key ? "Create another key →" : "Create key →"}
                  </button>
                </div>
              </div>
              {apiKeyOpen && (
                <div className="api-key-create">
                  <div className="api-key-grid">
                    <div className="form-row">
                      <label htmlFor="api-key-tenant" className="form-label">Tenant</label>
                      <input
                        id="api-key-tenant"
                        className="form-input"
                        value={apiTenantId}
                        onChange={(e) => setApiTenantId(e.target.value)}
                        maxLength={64}
                        placeholder="local"
                      />
                    </div>
                    <div className="form-row">
                      <label htmlFor="api-key-name" className="form-label">Key Name</label>
                      <input
                        id="api-key-name"
                        className="form-input"
                        value={apiKeyName}
                        onChange={(e) => setApiKeyName(e.target.value)}
                        maxLength={120}
                        placeholder="Browser session"
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={handleCreateApiKey}
                    disabled={apiKeyState === "creating" || !apiTenantId.trim() || (!authInfo.has_key && !canCreateApiKey)}
                    aria-busy={apiKeyState === "creating"}
                  >
                    {apiKeyState === "creating" ? "Creating…" : "Create API key"}
                  </button>
                  {!authInfo.has_key && !canCreateApiKey && (
                    <div className="form-error" role="alert">
                      Load an existing key first. First-key bootstrap is available only from localhost or deployment shell.
                    </div>
                  )}
                  {apiKeyError && <div className="form-error" role="alert">{apiKeyError}</div>}
                  {apiKeySuccess && <div className="form-success" role="status">{apiKeySuccess}</div>}
                  {createdApiKey && (
                    <div className="api-key-reveal">
                      <span>Created key</span>
                      <code>{createdApiKey}</code>
                      <button type="button" className="btn-link" onClick={handleCopyApiKey}>
                        {copyState === "copied" ? "Copied" : "Copy"}
                      </button>
                      {copyState === "error" && <span className="api-key-copy-error">Clipboard unavailable</span>}
                    </div>
                  )}
                  <div className="api-key-existing">
                    <label htmlFor="api-key-existing" className="form-label">Use Existing Key</label>
                    <div className="api-key-existing-row">
                      <input
                        id="api-key-existing"
                        className="form-input"
                        type="password"
                        value={existingApiKey}
                        onChange={(e) => setExistingApiKey(e.target.value)}
                        placeholder="concord_..."
                        autoComplete="off"
                      />
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={handleUseExistingApiKey}
                        disabled={existingKeyState === "verifying" || !existingApiKey.trim()}
                        aria-busy={existingKeyState === "verifying"}
                      >
                        {existingKeyState === "verifying" ? "Verifying…" : "Use key"}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
            <button
              type="button"
              className="btn-link import-toggle"
              onClick={() => setImportOpen((open) => !open)}
              aria-expanded={importOpen}
            >
              Import workflow contract →
            </button>
            {importOpen && (
              <div className="workflow-import-panel">
                <div className="form-row">
                  <label htmlFor="workflow-import-name" className="form-label">Workflow Name</label>
                  <input
                    id="workflow-import-name"
                    className="form-input"
                    value={importName}
                    onChange={(e) => setImportName(e.target.value)}
                    maxLength={120}
                    placeholder="CustomerSupportReview"
                  />
                </div>
                <div className="form-row">
                  <label htmlFor="workflow-import-spec" className="form-label">
                    Paste JSON workflow spec or YAML contract DSL
                  </label>
                  <textarea
                    id="workflow-import-spec"
                    className="form-textarea workflow-import-spec"
                    value={importSpec}
                    onChange={(e) => setImportSpec(e.target.value)}
                    maxLength={WORKFLOW_IMPORT_MAX}
                    rows={8}
                    placeholder={"contracts:\n  evidence:\n    id: C-EVD\n    rule: verified_sources_count must be > 0 before ReporterAgent runs"}
                  />
                  <div className="form-counter">{importSpec.length} / {WORKFLOW_IMPORT_MAX}</div>
                </div>
                {importError && (
                  <div className="form-error" role="alert" aria-live="polite">{importError}</div>
                )}
                {importSuccess && (
                  <div className="form-success" role="status" aria-live="polite">{importSuccess}</div>
                )}
                <div className="import-actions">
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={handleImportWorkflow}
                    disabled={importState === "submitting" || !importSpec.trim()}
                    aria-busy={importState === "submitting"}
                  >
                    {importState === "submitting" ? "Importing…" : "Import workflow"}
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="form-row">
            <label htmlFor="task-input" className="form-label">Task</label>
            <textarea
              id="task-input"
              className="form-textarea"
              value={task}
              onChange={(e) => setTask(e.target.value)}
              maxLength={TASK_MAX}
              rows={3}
              aria-required="true"
              placeholder="What is the agent supposed to do?"
            />
            <div className="form-counter">{task.length} / {TASK_MAX}</div>
          </div>

          <div className="form-row">
            <label htmlFor="research-question-input" className="form-label">Research Question</label>
            <textarea
              id="research-question-input"
              className="form-textarea"
              value={researchQuestion}
              onChange={(e) => setResearchQuestion(e.target.value)}
              maxLength={RESEARCH_QUESTION_MAX}
              rows={2}
              aria-required="true"
              placeholder="What concrete question should the swarm answer?"
            />
            <div className="form-counter">{researchQuestion.length} / {RESEARCH_QUESTION_MAX}</div>
          </div>

          {submitError && (
            <div className="form-error" role="alert" aria-live="polite">{submitError}</div>
          )}

          <div className="form-actions">
            <button
              type="button"
              className="btn-link"
              onClick={onSwitchToFixture}
            >
              View demo fixture run →
            </button>
            <button type="submit" className="btn-primary" disabled={!canSubmit} aria-busy={submitState === "submitting"}>
              {submitState === "submitting" ? "Submitting…" : "Run task"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ---------------- Sidebar (Phase 2) ----------------
   Run history fetched from /api/runs. Click to open ?run=ID.
   "Submit new" button returns to landing. */
function Sidebar({ currentRunId, onPickRun, onSubmitNew, onPickFixture, expanded, setExpanded }) {
  const [runs, setRuns] = useState([]);
  const [state, setState] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const hadCredentials = hasBrowserTenantCredentials();
        const status = await fetchApiKeyStatus();
        if (status && hadCredentials && status.requires_api_key && !status.authenticated) {
          clearBrowserAuth();
          if (!cancelled) {
            setRuns([]);
            setState("auth");
          }
          return;
        }
        if (status && !hadCredentials && statusBlocksProtectedFetch(status)) {
          if (!cancelled) {
            setRuns([]);
            setState("auth");
          }
          return;
        }
        const res = await fetch("/api/runs", { headers: liveHeaders() });
        if (!res.ok) throw new Error(`runs ${res.status}`);
        const body = await res.json();
        const ids = Array.isArray(body) ? body : (body.run_ids || body.runs || []);
        if (!cancelled) {
          setRuns(ids.slice(0, 20));
          setState("loaded");
        }
      } catch {
        if (!cancelled) setState("error");
      }
    }
    load();
    return () => { cancelled = true; };
  }, [currentRunId]);

  return (
    <aside className={`sidebar ${expanded ? "expanded" : "collapsed"}`} aria-label="Run history">
      <button
        type="button"
        className="sidebar-toggle"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
      >
        {expanded ? "◀" : "▶"}
      </button>
      {expanded && (
        <div className="sidebar-body">
          <div className="sidebar-section">
            <button type="button" className="btn-primary sidebar-cta" onClick={onSubmitNew}>+ New run</button>
          </div>
          <div className="sidebar-section">
            <h3 className="sidebar-heading">Recent runs</h3>
            {state === "loading" && <div className="sidebar-empty">Loading…</div>}
            {state === "auth" && <div className="sidebar-empty">API key required</div>}
            {state === "error" && <div className="sidebar-empty">Could not load runs</div>}
            {state === "loaded" && runs.length === 0 && <div className="sidebar-empty">No runs yet</div>}
            {state === "loaded" && runs.length > 0 && (
              <ul className="sidebar-runs">
                {runs.map((id) => (
                  <li key={id}>
                    <button
                      type="button"
                      className={`sidebar-run ${currentRunId === id ? "selected" : ""}`}
                      onClick={() => onPickRun(id)}
                    >
                      {id}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="sidebar-section">
            <button type="button" className="btn-link" onClick={onPickFixture}>Open fixture demo</button>
          </div>
        </div>
      )}
    </aside>
  );
}

function App() {
  // View state: "landing" (SubmitForm) | "dashboard" (legacy multi-screen view)
  // ?run=<id> or ?fixture=1 lands directly in dashboard mode; otherwise landing.
  const initialView = (() => {
    if (typeof window === "undefined") return "landing";
    const params = new URLSearchParams(window.location.search);
    if (params.get("run") || params.get("fixture") === "1") return "dashboard";
    return "landing";
  })();
  const [view, setView] = useState(initialView);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [currentRunId, setCurrentRunId] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("run") || null;
  });

  function navigateToRun(runId) {
    const url = new URL(window.location.href);
    url.searchParams.set("run", runId);
    url.searchParams.delete("fixture");
    window.history.pushState({}, "", url);
    setCurrentRunId(runId);
    setView("dashboard");
  }
  function navigateToFixture() {
    const url = new URL(window.location.href);
    url.searchParams.set("fixture", "1");
    url.searchParams.delete("run");
    window.history.pushState({}, "", url);
    setCurrentRunId(null);
    setView("dashboard");
  }
  function navigateToLanding() {
    const url = new URL(window.location.href);
    url.searchParams.delete("run");
    url.searchParams.delete("fixture");
    window.history.pushState({}, "", url);
    setCurrentRunId(null);
    setView("landing");
  }

  if (view === "landing") {
    return (
      <div className="shell shell-landing">
        <Sidebar
          currentRunId={null}
          onPickRun={navigateToRun}
          onSubmitNew={navigateToLanding}
          onPickFixture={navigateToFixture}
          expanded={sidebarExpanded}
          setExpanded={setSidebarExpanded}
        />
        <SubmitForm
          onSubmitted={navigateToRun}
          onSwitchToFixture={navigateToFixture}
        />
      </div>
    );
  }

  return <Dashboard
    onSubmitNew={navigateToLanding}
    onPickRun={navigateToRun}
    onPickFixture={navigateToFixture}
    sidebarExpanded={sidebarExpanded}
    setSidebarExpanded={setSidebarExpanded}
    currentRunIdFromUrl={currentRunId}
  />;
}

function Dashboard({ onSubmitNew, onPickRun, onPickFixture, sidebarExpanded, setSidebarExpanded, currentRunIdFromUrl }) {
  const [screen, setScreen] = useState("overview");
  const [selectedPatch, setSelectedPatch] = useState(null);
  const [appliedPatches, setAppliedPatches] = useState([]);
  const initialMode = currentRunIdFromUrl ? "live" : "fixture";
  const [data, setData] = useState(FIXTURE_DATA);
  const [sourceMode, setSourceMode] = useState(initialMode);
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
    <div className="shell shell-with-sidebar" data-screen-label={SCREENS.find(s=>s.id===screen).num + " " + SCREENS.find(s=>s.id===screen).label}>
      <Sidebar
        currentRunId={currentRunIdFromUrl}
        onPickRun={onPickRun}
        onSubmitNew={onSubmitNew}
        onPickFixture={onPickFixture}
        expanded={sidebarExpanded}
        setExpanded={setSidebarExpanded}
      />
      <div className="shell-main">
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
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
