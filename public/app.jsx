/* global React, ReactDOM */
const { useState, useEffect, useMemo } = React;
const D = window.CONCORD_DATA;

const SCREENS = [
  { id: "overview",   num: "01", label: "Overview" },
  { id: "trace",      num: "02", label: "Agent Trace" },
  { id: "violations", num: "04", label: "Violations" },
  { id: "repair",     num: "04", label: "Repair Patch" },
  { id: "regression", num: "05", label: "Regression" },
  { id: "report",     num: "06", label: "Final Report" },
  { id: "submit",     num: "07", label: "Submit Run" },
  { id: "workflows",  num: "08", label: "Workflows" },
];

const TASK_MAX = 1000;
const RESEARCH_QUESTION_MAX = 500;

const TERMINAL_STATUSES = new Set(["completed", "failed"]);
const STATUS_KIND = {
  queued: "neutral",
  analyzing: "warn",
  repairing: "warn",
  testing: "warn",
  completed: "ok",
  failed: "err",
};
const SSE_MAX_RECONNECTS = 5;
const SSE_BACKOFF_BASE_MS = 500;

/**
 * Live SSE consumer for /api/runs/{id}/events.
 *
 * Returns { status, lastEvent, connectionState, error, lastEventId }.
 *
 * - Opens EventSource against the SSE endpoint with the stream_token
 * - Tracks the current status from each event payload
 * - Reconnects on disconnect using Last-Event-ID via the URL (browser
 *   EventSource doesn't expose request headers, so we pass it as a query
 *   param the server can read OR rely on its native Last-Event-ID header
 *   on auto-reconnect — we do both)
 * - Exponential backoff up to SSE_MAX_RECONNECTS attempts
 * - Cleans up on unmount or terminal status
 *
 * `eventSourceCtor` is injectable for tests (jsdom has no native EventSource).
 */
function useRunEventStream(runId, streamToken, options = {}) {
  const eventSourceCtor = options.eventSourceCtor || (typeof EventSource !== "undefined" ? EventSource : null);
  const [status, setStatus] = useState(null);
  const [lastEventId, setLastEventId] = useState(0);
  const [connectionState, setConnectionState] = useState("idle"); // idle|connecting|open|reconnecting|closed|error
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!runId || !streamToken) return undefined;
    if (!eventSourceCtor) {
      setError(new Error("EventSource not available"));
      setConnectionState("error");
      return undefined;
    }

    let attempt = 0;
    let es = null;
    let cancelled = false;
    let reconnectTimer = null;
    let lastSeenId = 0;

    function open() {
      const url = `/api/runs/${runId}/events?stream_token=${encodeURIComponent(streamToken)}`
        + (lastSeenId > 0 ? `&last_event_id=${lastSeenId}` : "");
      setConnectionState(attempt === 0 ? "connecting" : "reconnecting");
      es = new eventSourceCtor(url);

      es.onopen = () => {
        if (cancelled) return;
        attempt = 0;
        setConnectionState("open");
      };

      const handleEvent = (event) => {
        if (cancelled) return;
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.status) setStatus(parsed.status);
          if (parsed.sequence) {
            lastSeenId = Number(parsed.sequence);
            setLastEventId(lastSeenId);
          }
          if (parsed.status && TERMINAL_STATUSES.has(parsed.status)) {
            es.close();
            setConnectionState("closed");
          }
        } catch (e) {
          // Malformed event — log via setError but don't tear down
          setError(e);
        }
      };
      // Listen for both default 'message' and the named events the API emits
      es.onmessage = handleEvent;
      ["status", "queued", "analyzing", "repairing", "testing", "completed", "failed"].forEach(name => {
        es.addEventListener(name, handleEvent);
      });

      es.onerror = () => {
        if (cancelled) return;
        es.close();
        if (attempt >= SSE_MAX_RECONNECTS) {
          setConnectionState("error");
          setError(new Error(`SSE failed after ${SSE_MAX_RECONNECTS} reconnect attempts`));
          return;
        }
        attempt += 1;
        const delay = SSE_BACKOFF_BASE_MS * Math.pow(2, attempt - 1);
        setConnectionState("reconnecting");
        reconnectTimer = setTimeout(open, delay);
      };
    }

    open();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (es) es.close();
    };
  }, [runId, streamToken, eventSourceCtor]);

  return { status, lastEventId, connectionState, error };
}

function _formatElapsed(ms) {
  if (!ms || ms < 0) return "0:00";
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function RunProgress({ runId, streamToken, eventSourceCtor }) {
  const { status, connectionState, error } = useRunEventStream(runId, streamToken, { eventSourceCtor });
  const [startedAt] = useState(Date.now());
  const [, setNow] = useState(Date.now());

  useEffect(() => {
    if (!status || TERMINAL_STATUSES.has(status)) return undefined;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [status]);

  if (!runId || !streamToken) return null;
  if (status && TERMINAL_STATUSES.has(status)) {
    // Auto-hide after a small delay would be nice, but for forensic UX
    // we keep the terminal state visible so the user sees the outcome.
    return (
      <div className={`run-progress run-progress-${STATUS_KIND[status] || "neutral"}`} aria-live="polite">
        <span className="run-progress-pill" data-status={status}>{status}</span>
        <span className="run-progress-runid">{runId}</span>
      </div>
    );
  }

  const kind = STATUS_KIND[status || "queued"] || "neutral";
  const label = status || "queued";
  return (
    <div className={`run-progress run-progress-${kind}`} role="status" aria-live="polite">
      <span className="run-progress-pill" data-status={label}>{label}</span>
      <span className="run-progress-runid">{runId}</span>
      <span className="run-progress-elapsed">{_formatElapsed(Date.now() - startedAt)}</span>
      {connectionState === "reconnecting" && (
        <span className="run-progress-reconnect">reconnecting…</span>
      )}
      {error && (
        <span className="run-progress-error" role="alert">{error.message}</span>
      )}
    </div>
  );
}

async function fetchStreamToken(runId) {
  const res = await fetch(`/api/runs/${runId}/events/token`, { method: "POST" });
  if (!res.ok) throw new Error(`stream token fetch ${res.status}`);
  const body = await res.json();
  return body.stream_token;
}

function Sq({ kind }) { return <span className={`sq ${kind}`}></span>; }
function Pill({ kind, children }) {
  return <span className={`pill ${kind}`}><Sq kind={kind} />{children}</span>;
}

function StatusCluster({ screen }) {
  const onReport = screen === "report";
  const text = onReport ? "RERUN READY" : "4 VIOLATIONS DETECTED";
  const klass = onReport ? "ok" : "fail";
  return (
    <div className="status-cluster">
      <div className="status-line">
        <span className={`status-dot ${onReport ? "ok" : "fail"}`}></span>
        <span className={`status-text ${klass}`}>{text}</span>
        <span className="cursor"></span>
      </div>
      <div className="status-line muted" style={{fontSize: 11, letterSpacing: "0.14em"}}>
        14:22:26 UTC
      </div>
    </div>
  );
}

function TopBar({ screen, setScreen }) {
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
      <StatusCluster screen={screen} />
    </header>
  );
}

function MetaStrip() {
  const r = D.run;
  return (
    <div className="meta-strip">
      <div className="meta-cell"><span className="lbl">Run</span><span className="val">{r.id}</span></div>
      <div className="meta-cell"><span className="lbl">Workflow</span><span className="val">{r.workflow}</span></div>
      <div className="meta-cell"><span className="lbl">Pattern</span><span className="val">{r.pattern}</span></div>
      <div className="meta-cell"><span className="lbl">Manager</span><span className="val">{r.manager}</span></div>
      <div className="meta-cell"><span className="lbl">Duration</span><span className="val">{(r.duration_ms/1000).toFixed(2)}s</span></div>
      <div className="meta-cell"><span className="lbl">Operator</span><span className="val">{r.operator}</span></div>
    </div>
  );
}

/* ---------------- OVERVIEW ---------------- */
function Overview({ setScreen }) {
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
        <h2>Agent Pipeline</h2>
        <div className="right">click an agent to inspect trace</div>
      </div>
      <div className="pipeline" style={{marginBottom: 22}}>
        {D.agents.map((a, i) => (
          <button
            key={a.id}
            className={`agent-box ${a.status === "FAIL" ? "fail" : "pass"}`}
            onClick={() => setScreen("trace")}
            title={`Open trace · ${a.name}`}
          >
            <div>
              <div className="head">
                <span className="id">{String(i+1).padStart(2,"0")} · {a.id}</span>
                <span className="muted" style={{fontSize: 10.5}}>{a.steps} step{a.steps!==1?"s":""}</span>
              </div>
              <div className="name">{a.name}</div>
              <div className="note">{a.note}</div>
            </div>
            <div className="stat-line">
              <Sq kind={a.status === "FAIL" ? "fail" : "pass"} />
              <span className={a.status === "FAIL" ? "text-brick" : "text-sage"}>{a.status}</span>
            </div>
          </button>
        ))}
      </div>

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

/* ---------------- TRACE ---------------- */
function Trace() {
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
              <tr key={e.step} className={`trace-row ${e.status === "FAIL" ? "fail" : e.status === "WARN" ? "warn" : ""}`}>
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
      <div style={{marginTop: 12, color: "var(--text-3)", fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase"}}>
        end of trace &nbsp;&middot;&nbsp; final_output emitted at step 11 &nbsp;&middot;&nbsp; side_effect attempted at step 12
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
function Repair({ selectedPatch, setSelectedPatch }) {
  return (
    <>
      <div className="section-head">
        <h2>Repair Patch &nbsp;//&nbsp; AG2-native primitives</h2>
        <div className="right">{D.patches.length} patches &nbsp;&middot;&nbsp; mapped from {D.violations.length} violations</div>
      </div>
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

      {D.patches
        .filter(p => selectedPatch === null || selectedPatch === p.id)
        .map(p => {
        const v = D.violations.find(v => v.id === p.violation);
        return (
          <div key={p.id} className="patch-block">
            <div className="patch-head">
              <div className="id">{p.id}</div>
              <div>
                <div className="ctitle">{p.title}</div>
                <div className="muted" style={{fontSize: 11, marginTop: 4}}>fixes <span className="text-brick">{v.id}</span> &nbsp;&middot;&nbsp; {v.type} CONTRACT &nbsp;&middot;&nbsp; failed at step {v.failed_step}</div>
              </div>
              <div className="prim">{p.primitive}</div>
              <div><Pill kind="ok">READY</Pill></div>
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
function _approvalKind(status) {
  const norm = (status || "").toUpperCase();
  if (norm.startsWith("APPROVED")) return "ok";
  if (norm.startsWith("REJECTED")) return "err";
  return "warn"; // PENDING* / unknown
}

function _isPendingApproval(status) {
  const norm = (status || "").toUpperCase();
  return norm.startsWith("PENDING") || norm === "" || norm === "UNKNOWN";
}

function ApprovalPanel({ runId, approval, onUpdated }) {
  const [operator, setOperator] = useState(approval?.operator || "j.kowalski");
  const [comments, setComments] = useState(approval?.comments || "");
  const [submitState, setSubmitState] = useState("idle"); // idle|submitting|error
  const [submitError, setSubmitError] = useState("");

  const status = approval?.status || "UNKNOWN";
  const pending = _isPendingApproval(status);
  const kind = _approvalKind(status);

  async function decide(decision) {
    if (!runId) {
      setSubmitError("No run_id available — submit a run first.");
      setSubmitState("error");
      return;
    }
    setSubmitState("submitting");
    setSubmitError("");
    try {
      const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, operator, comments }),
      });
      if (res.status === 404) {
        setSubmitError(`Run ${runId} not found. It may have been deleted.`);
        setSubmitState("error");
        return;
      }
      if (res.status === 409) {
        const body = await res.json().catch(() => ({}));
        setSubmitError(`Run is not approval-ready: ${body.detail || res.statusText}`);
        setSubmitState("error");
        return;
      }
      if (!res.ok) {
        setSubmitError(`Server error ${res.status}. Try again.`);
        setSubmitState("error");
        return;
      }
      const body = await res.json();
      setSubmitState("idle");
      if (onUpdated) onUpdated(body.approval);
    } catch (err) {
      setSubmitError(`Network error: ${err.message || err}`);
      setSubmitState("error");
    }
  }

  return (
    <div className={`approval approval-${kind}`}>
      <div className="big">
        <span className="sq"></span>
        <span className="label" data-status={status}>{status.replace(/_/g, " ")}</span>
      </div>
      <div className="kv-list">
        <div className="lbl">Operator</div>
        <div className="val">{approval?.operator || "—"}</div>
        <div className="lbl">Requested</div>
        <div className="val">{approval?.requested_at || "—"}</div>
        <div className="lbl">SLA</div>
        <div className="val">{approval?.sla || "—"}</div>
        <div className="lbl">Channel</div>
        <div className="val">UserProxyAgent / HumanGate</div>
      </div>

      {approval?.comments && (
        <>
          <hr />
          <div className="approval-comments-display">
            <div className="lbl">Comments</div>
            <div className="val">{approval.comments}</div>
          </div>
        </>
      )}

      <hr />

      {pending && (
        <form className="approval-form" onSubmit={(e) => e.preventDefault()} aria-label="Approval form">
          <label className="form-row">
            <span className="form-label">Operator</span>
            <input
              className="form-input"
              type="text"
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              aria-required="true"
            />
          </label>
          <label className="form-row">
            <span className="form-label">Comments (optional)</span>
            <textarea
              className="form-textarea"
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              rows={2}
              maxLength={500}
              placeholder="Optional context for the audit trail"
            />
          </label>

          {submitError && (
            <div className="form-error" role="alert" aria-live="polite">
              {submitError}
              <button
                type="button"
                className="btn-retry"
                onClick={() => { setSubmitState("idle"); setSubmitError(""); }}
              >
                dismiss
              </button>
            </div>
          )}

          <div className="btn-row">
            <button
              type="button"
              className="btn"
              disabled={!operator.trim() || submitState === "submitting"}
              onClick={() => decide("approved")}
              aria-busy={submitState === "submitting"}
            >
              {submitState === "submitting" ? "SUBMITTING…" : "APPROVE & RERUN"}
            </button>
            <button
              type="button"
              className="btn ghost"
              disabled={!operator.trim() || submitState === "submitting"}
              onClick={() => decide("rejected")}
              aria-busy={submitState === "submitting"}
            >
              REJECT
            </button>
          </div>
        </form>
      )}

      {!pending && submitError && (
        <div className="form-error" role="alert" aria-live="polite">{submitError}</div>
      )}
    </div>
  );
}

function Report({ setScreen, runId }) {
  const [reportData, setReportData] = useState(D.report);
  const r = reportData;

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
        <ApprovalPanel
          runId={runId || D.run?.id}
          approval={r.approval}
          onUpdated={(updated) => setReportData({ ...reportData, approval: { ...r.approval, ...updated } })}
        />
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

/* ---------------- WORKFLOWS ---------------- */
function WorkflowsScreen({ setScreen, onPickWorkflow }) {
  const [workflows, setWorkflows] = useState([]);
  const [state, setState] = useState("loading"); // loading|loaded|error
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailState, setDetailState] = useState("idle");
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/workflows");
        if (!res.ok) throw new Error(`workflows fetch ${res.status}`);
        const body = await res.json();
        const list = Array.isArray(body) ? body : (body.workflows || []);
        if (!cancelled) {
          setWorkflows(list);
          setState("loaded");
        }
      } catch (err) {
        if (!cancelled) {
          setError(String(err.message || err));
          setState("error");
        }
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  async function loadDetail(workflowId) {
    setSelectedId(workflowId);
    setDetail(null);
    setDetailState("loading");
    setDetailError("");
    try {
      const res = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}`);
      if (res.status === 404) {
        setDetailError(`Workflow ${workflowId} doesn't exist or was deleted.`);
        setDetailState("error");
        return;
      }
      if (!res.ok) {
        setDetailError(`Server error ${res.status} loading workflow detail.`);
        setDetailState("error");
        return;
      }
      const body = await res.json();
      setDetail(body);
      setDetailState("loaded");
    } catch (err) {
      setDetailError(`Network error: ${err.message || err}`);
      setDetailState("error");
    }
  }

  function _id(wf) { return wf.workflow_id || wf.id; }
  function _name(wf) { return wf.name || _id(wf); }
  function _agentCount(wf) { return (wf.agents || []).length; }
  function _contractCount(wf) { return (wf.contracts || []).length; }

  return (
    <>
      <div className="section-head">
        <h2>Workflows &nbsp;//&nbsp; registered topology</h2>
        <div className="right">
          {state === "loaded" ? `${workflows.length} workflow${workflows.length === 1 ? "" : "s"}` : ""}
        </div>
      </div>

      {state === "loading" && (
        <div className="workflows-loading" role="status" aria-live="polite">Loading workflows…</div>
      )}

      {state === "error" && (
        <div className="workflows-error" role="alert">
          Could not load workflows: {error}
        </div>
      )}

      {state === "loaded" && workflows.length === 0 && (
        <div className="workflows-empty">
          <h3>No workflows registered yet</h3>
          <p>
            Register a workflow via <code>POST /api/workflows</code> first, then submit a
            run against it from the <button className="btn-link" onClick={() => setScreen("submit")}>Submit Run</button> screen.
          </p>
        </div>
      )}

      {state === "loaded" && workflows.length > 0 && (
        <div className="workflows-grid">
          <div className="workflows-list" role="list" aria-label="Registered workflows">
            {workflows.map(wf => (
              <button
                key={_id(wf)}
                role="listitem"
                className={`workflow-row ${selectedId === _id(wf) ? "selected" : ""}`}
                onClick={() => loadDetail(_id(wf))}
              >
                <div className="workflow-row-name">{_name(wf)}</div>
                <div className="workflow-row-id">{_id(wf)}</div>
                <div className="workflow-row-meta">
                  {_agentCount(wf)} agent{_agentCount(wf) === 1 ? "" : "s"}
                  &nbsp;·&nbsp; {_contractCount(wf)} contract{_contractCount(wf) === 1 ? "" : "s"}
                </div>
                {wf.owner && <div className="workflow-row-owner">{wf.owner}</div>}
              </button>
            ))}
          </div>

          <div className="workflow-detail" aria-live="polite">
            {!selectedId && (
              <div className="workflow-detail-empty">Pick a workflow on the left.</div>
            )}
            {selectedId && detailState === "loading" && (
              <div role="status">Loading workflow detail…</div>
            )}
            {selectedId && detailState === "error" && (
              <div role="alert" className="workflows-error">{detailError}</div>
            )}
            {selectedId && detailState === "loaded" && detail && (
              <>
                <div className="workflow-detail-head">
                  <h3>{detail.name || detail.workflow_id}</h3>
                  <span className="muted">{detail.workflow_id}</span>
                </div>

                <section className="workflow-section">
                  <h4>Topology</h4>
                  <pre className="topology-preview">{JSON.stringify(detail.declared_topology || {}, null, 2)}</pre>
                </section>

                <section className="workflow-section">
                  <h4>Agents ({(detail.agents || []).length})</h4>
                  <ul className="workflow-agent-list">
                    {(detail.agents || []).map((a, i) => (
                      <li key={a.name || i}>{a.name || JSON.stringify(a)}</li>
                    ))}
                  </ul>
                </section>

                <section className="workflow-section">
                  <h4>Contracts ({(detail.contracts || []).length})</h4>
                  <ul className="workflow-contract-list">
                    {(detail.contracts || []).map((c, i) => (
                      <li key={c.id || i}>
                        <span className="contract-id">{c.id || `C-${i + 1}`}</span>
                        <span className="contract-type">{c.type || "—"}</span>
                        <span className="contract-rule">{c.rule || ""}</span>
                      </li>
                    ))}
                  </ul>
                </section>

                <div className="btn-row">
                  <button
                    className="btn"
                    onClick={() => {
                      if (onPickWorkflow) onPickWorkflow(detail);
                      setScreen("submit");
                    }}
                  >
                    SUBMIT RUN AGAINST THIS WORKFLOW
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

/* ---------------- SUBMIT RUN ---------------- */
function SubmitRun({ setScreen, onRunSubmitted }) {
  const [workflows, setWorkflows] = useState([]);
  const [workflowsState, setWorkflowsState] = useState("loading"); // loading|loaded|error
  const [workflowsError, setWorkflowsError] = useState("");
  const [workflowId, setWorkflowId] = useState("");
  const [task, setTask] = useState("");
  const [researchQuestion, setResearchQuestion] = useState("");
  const [mode, setMode] = useState("stub");
  const [submitState, setSubmitState] = useState("idle"); // idle|submitting|error
  const [submitError, setSubmitError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/workflows");
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
  }, []);

  const validate = () => {
    const errs = {};
    if (!workflowId) errs.workflow = "Pick a workflow";
    if (!task.trim()) errs.task = "Task is required";
    else if (task.length > TASK_MAX) errs.task = `Task must be ≤ ${TASK_MAX} chars`;
    if (!researchQuestion.trim()) errs.research_question = "Research question is required";
    else if (researchQuestion.length > RESEARCH_QUESTION_MAX) errs.research_question = `Question must be ≤ ${RESEARCH_QUESTION_MAX} chars`;
    return errs;
  };

  const errors = validate();
  const canSubmit = Object.keys(errors).length === 0 && submitState !== "submitting";

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = validate();
    setFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitState("submitting");
    setSubmitError("");
    try {
      const res = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_id: workflowId,
          task_spec: { task: task.trim(), research_question: researchQuestion.trim(), mode },
        }),
      });
      if (res.status === 422 || res.status === 400) {
        const body = await res.json().catch(() => ({}));
        setSubmitError(`Validation error: ${body.detail || res.statusText}`);
        setSubmitState("error");
        return;
      }
      if (res.status === 404) {
        setSubmitError(`Workflow ${workflowId} not found. Refresh the workflow list.`);
        setSubmitState("error");
        return;
      }
      if (!res.ok) {
        setSubmitError(`Server error ${res.status}. Try again or check the API.`);
        setSubmitState("error");
        return;
      }
      const body = await res.json();
      const runId = body.run_id;
      setSubmitState("idle");
      if (onRunSubmitted) onRunSubmitted(runId);
      if (setScreen) setScreen("trace");
    } catch (err) {
      setSubmitError(`Network error: ${err.message || err}`);
      setSubmitState("error");
    }
  }

  return (
    <>
      <div className="section-head">
        <h2>Submit Run &nbsp;//&nbsp; new task_spec</h2>
        <div className="right">stub mode runs locally · live mode hits the AG2 swarm</div>
      </div>

      <form className="submit-run-form" onSubmit={handleSubmit} aria-label="Submit run form">
        <div className="form-row">
          <label htmlFor="workflow-picker" className="form-label">Workflow</label>
          {workflowsState === "loading" && <div className="form-loading" role="status">Loading workflows…</div>}
          {workflowsState === "error" && (
            <div className="form-error" role="alert">
              Could not load workflows: {workflowsError}
            </div>
          )}
          {workflowsState === "loaded" && workflows.length === 0 && (
            <div className="form-empty">No workflows registered yet. Register one first.</div>
          )}
          {workflowsState === "loaded" && workflows.length > 0 && (
            <select
              id="workflow-picker"
              className="form-select"
              value={workflowId}
              onChange={(e) => setWorkflowId(e.target.value)}
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.workflow)}
            >
              {workflows.map(wf => (
                <option key={wf.workflow_id || wf.id} value={wf.workflow_id || wf.id}>
                  {wf.name || wf.workflow_id || wf.id}
                </option>
              ))}
            </select>
          )}
          {fieldErrors.workflow && <div className="form-field-error">{fieldErrors.workflow}</div>}
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
            aria-invalid={Boolean(fieldErrors.task)}
            aria-describedby="task-counter task-error"
            placeholder="What is the agent supposed to do?"
          />
          <div id="task-counter" className="form-counter">{task.length} / {TASK_MAX}</div>
          {fieldErrors.task && <div id="task-error" className="form-field-error">{fieldErrors.task}</div>}
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
            aria-invalid={Boolean(fieldErrors.research_question)}
            aria-describedby="rq-counter rq-error"
            placeholder="What concrete question should the swarm answer?"
          />
          <div id="rq-counter" className="form-counter">{researchQuestion.length} / {RESEARCH_QUESTION_MAX}</div>
          {fieldErrors.research_question && <div id="rq-error" className="form-field-error">{fieldErrors.research_question}</div>}
        </div>

        <fieldset className="form-row form-mode" aria-required="true">
          <legend className="form-label">Mode</legend>
          <label className="form-radio">
            <input
              type="radio"
              name="mode"
              value="stub"
              checked={mode === "stub"}
              onChange={(e) => setMode(e.target.value)}
            />
            <span><strong>stub</strong> — deterministic, no LLM</span>
          </label>
          <label className="form-radio">
            <input
              type="radio"
              name="mode"
              value="live"
              checked={mode === "live"}
              onChange={(e) => setMode(e.target.value)}
            />
            <span><strong>live</strong> — real AG2 swarm + Tavily + LLM</span>
          </label>
        </fieldset>

        {submitError && (
          <div className="form-error" role="alert" aria-live="polite">
            {submitError}
          </div>
        )}

        <div className="form-actions">
          <button
            type="submit"
            className="btn-primary"
            disabled={!canSubmit}
            aria-busy={submitState === "submitting"}
          >
            {submitState === "submitting" ? "Submitting…" : "Submit run"}
          </button>
        </div>
      </form>
    </>
  );
}

/* ---------------- APP ---------------- */
function App() {
  const [screen, setScreen] = useState("overview");
  const [selectedPatch, setSelectedPatch] = useState(null);
  const [currentRunId, setCurrentRunId] = useState(null);
  const [streamToken, setStreamToken] = useState(null);
  const [streamTokenError, setStreamTokenError] = useState(null);

  // when leaving repair screen, clear filter
  useEffect(() => { if (screen !== "repair") setSelectedPatch(null); }, [screen]);

  // Fetch a stream token whenever a fresh run is submitted so the SSE
  // consumer can authenticate without leaking the API key into a URL.
  useEffect(() => {
    if (!currentRunId) {
      setStreamToken(null);
      return undefined;
    }
    let cancelled = false;
    fetchStreamToken(currentRunId)
      .then((token) => {
        if (!cancelled) {
          setStreamToken(token);
          setStreamTokenError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setStreamTokenError(err);
          setStreamToken(null);
        }
      });
    return () => { cancelled = true; };
  }, [currentRunId]);

  const handleRunSubmitted = (runId) => {
    setCurrentRunId(runId);
  };

  return (
    <div className="shell" data-screen-label={SCREENS.find(s=>s.id===screen).num + " " + SCREENS.find(s=>s.id===screen).label}>
      <TopBar screen={screen} setScreen={setScreen} />
      <MetaStrip />
      {currentRunId && (
        <RunProgress runId={currentRunId} streamToken={streamToken} />
      )}
      {streamTokenError && (
        <div className="run-progress run-progress-err" role="alert">
          stream token failed: {streamTokenError.message}
        </div>
      )}
      <main className="main">
        {screen === "overview"   && <Overview setScreen={setScreen} />}
        {screen === "trace"      && <Trace />}
        {screen === "violations" && <Violations setScreen={setScreen} setSelectedPatch={setSelectedPatch} />}
        {screen === "repair"     && <Repair selectedPatch={selectedPatch} setSelectedPatch={setSelectedPatch} />}
        {screen === "regression" && <Regression />}
        {screen === "report"     && <Report setScreen={setScreen} runId={currentRunId} />}
        {screen === "submit"     && <SubmitRun setScreen={setScreen} onRunSubmitted={handleRunSubmitted} />}
        {screen === "workflows"  && <WorkflowsScreen setScreen={setScreen} />}
      </main>
    </div>
  );
}

const _rootEl = typeof document !== "undefined" ? document.getElementById("root") : null;
if (_rootEl) {
  ReactDOM.createRoot(_rootEl).render(<App />);
}

export {
  App, Overview, Trace, Violations, Repair, Regression, Report, SubmitRun,
  WorkflowsScreen,
  RunProgress, useRunEventStream, fetchStreamToken,
  ApprovalPanel,
  TERMINAL_STATUSES, STATUS_KIND, SSE_MAX_RECONNECTS,
  SCREENS,
};
