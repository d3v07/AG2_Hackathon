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
];

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

  // when leaving repair screen, clear filter
  useEffect(() => { if (screen !== "repair") setSelectedPatch(null); }, [screen]);

  return (
    <div className="shell" data-screen-label={SCREENS.find(s=>s.id===screen).num + " " + SCREENS.find(s=>s.id===screen).label}>
      <TopBar screen={screen} setScreen={setScreen} />
      <MetaStrip />
      <main className="main">
        {screen === "overview"   && <Overview setScreen={setScreen} />}
        {screen === "trace"      && <Trace />}
        {screen === "violations" && <Violations setScreen={setScreen} setSelectedPatch={setSelectedPatch} />}
        {screen === "repair"     && <Repair selectedPatch={selectedPatch} setSelectedPatch={setSelectedPatch} />}
        {screen === "regression" && <Regression />}
        {screen === "report"     && <Report setScreen={setScreen} />}
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
