# Concord Lite — Demo Script & Q&A Cue Cards

Pull this up on a second screen. Every line in **bold quotes** is verbatim — say it that way.

---

## OPENING (30 seconds, before clicking anything)

1. **"Multi-agent systems fail silently. An agent says 'I verified the sources' and writes `verified_sources_count = 0`. An action agent saves a report without waiting for human approval. The narrative says one thing, the trace says another."**

2. **"Concord Lite is a 7-agent diagnostic pipeline that watches a multi-agent workflow run, catches every contract violation in the trace, attributes it to the responsible agent, generates an AG2-native repair, validates the repair in a Daytona sandbox, and produces a Contract Violation Report — fully automated."**

3. **"We didn't build a better workflow. We built a referee for any AG2 workflow."**

4. **"Live URL is concord-lite.vercel.app. Backend pipeline is `python run_all.py --fixture` — runs end-to-end with no API keys."**

---

## ARCHITECTURE OVERVIEW (before the screen tour)

5. **"Two zones. Zone A is the target workflow being audited — a Literature Review Assistant with 5 agents that's broken by design. Zone B is Concord — 7 diagnostic agents that read Zone A's trace and produce a report."**

6. **"Key separation: contracts are declared in Zone A, verified in Zone B. The workflow can't audit itself."**

7. **"Both zones use AG2 — `ConversableAgent`, `UserProxyAgent`, real `human_input_mode='ALWAYS'` for human gates. LLM is Gemini 2.5 Flash via OpenRouter. Tavily for live web search in Zone A. Daytona for sandboxed regression testing in Zone B."**

---

## SCREEN-BY-SCREEN WALK (the live demo)

### Screen 1 — Workflows
8. **(open Workflows screen)** **"This is the workflow registry. Pick Literature Review Assistant."**

9. **(click Submit Run)** **"The run form pre-fills with the Literature Review task. There is no mode picker — product submissions use the live AG2 path. Click Submit."**

10. **"Watch the SSE progress strip: queued → analyzing → completed. That's the full Zone B pipeline running live — TraceCollector, ContractChecker, Attribution, Repair, RegressionTest, Reporter, HumanGate — seven agents in sequence."**

### Screen 2 — Overview
11. **"This is Zone B's report rendered on top of Zone A's execution. The 5 agents you see ARE Zone A — Researcher, Critic, Verifier, Reporter, Action. Zone B added the violation count, the contract status table, and the severity breakdown."**

12. **(click REPLAY RUN)** **"This is the recorded trace playing back. Twelve events, ~520 milliseconds per step. Researcher and Critic pass. Verifier turns red — that's where the contract failure happens. Reporter and Action both fail downstream."**

13. **"Bottom-right of each agent: the per-agent footer. 'no tool_event' under Verifier, 'verified=0' under Reporter, 'approval=pending' under Action. These are the failures we'll trace through the rest of the demo."**

### Screen 3 — Forensic (available once PR #110-#113 land)
14. **(click Forensic screen)** **"This is the span tree for the workflow run. Every agent turn, tool call, handoff, and guardrail check is a span. The tree shows the full execution path."**

15. **(click VerifierAgent span)** **"The inspector opens on the right. Eight sections: Identity, Timing, Error, Input, Output, Attributes, Contract violations, Repair, Regression. VerifierAgent has two contract violations — C-TOL and C-EVD — with deep-links."**

16. **(click a violation in the inspector)** **"That deep-link jumps directly to the Violations screen with the matching violation highlighted."**

### Screen 4 — Violations
17. **(click 04 Violations)** **"Four violations, three HIGH severity, one MED. Each card has the contract that failed, what was expected, what was observed, the failed agent, and an evidence chain pointing back to the trace steps."**

18. **(click any violation row)** **"Clicking a violation jumps you straight to the proposed repair patch — that's the operator workflow."**

### Screen 5 — Repair Patch
19. **"Four AG2-native primitive patches. Guardrail, ToolGate, OnContextCondition, and UserProxyAgent slash HumanGate. Each one shows before / after — red lines are removed, green lines are added."**

20. **"These aren't pseudo-code. The added lines paste straight into the operator's `ConversableAgent(...)` constructor or `Handoffs(...)` call. The repair targets the AG2 framework primitive, not the user's business logic."**

21. **"P-001 adds a Guardrail to Reporter — `condition=lambda ctx: ctx['verified_sources_count'] > 0`. P-002 wraps Verifier's `emit_verdict` in a tool-event check. P-003 gates the Verifier→Reporter handoff with `OnContextCondition`. P-004 inserts a UserProxyAgent with `human_input_mode='ALWAYS'` before Action."**

22. **(click patch link "Open on Regression screen")** **"That link jumps directly to the Regression screen for this patch."**

### Screen 6 — Regression
23. **(click 06 Regression)** **"This is the Daytona sandbox. Per-run isolation, fresh `python:3.11-slim` image, sandbox ID `dt-9f3a-2b71`. The terminal stream is captured stdout from `sandbox.process.code_run`."**

24. **"Four assertions, all PASS. The LLM generated the test code. Daytona executed it. We always delete the sandbox in `finally` — no resource leak, no cleanup burden on the operator."**

25. **"This is where Daytona earns its keep. We're executing LLM-generated code — running that on the operator's machine is unsafe."**

### Screen 7 — Final Report
26. **(click 07 Final Report)** **"Notice the top-right status flipped from '4 VIOLATIONS DETECTED' in red to 'RERUN READY' in green. That's the explicit signal the loop is closed."**

27. **"Executive summary is LLM-generated narrative. Approval block shows PENDING_OPERATOR. Click Approve — the status flips to APPROVED and the decision is persisted via `POST /api/runs/{run_id}/approval`."**

28. **"Patches Applied table is the deterministic part — four AG2 primitives mapped to four contract types."**

---

## CONTRACTS — WHERE THEY LIVE (must-know, very likely Q&A)

26. **"Contracts are declared in Zone A's `workflow_contract.py` as a plain manifest — five rules with IDs C1 through C5, types, and severities. That's the workflow author's promise."**

27. **"Contracts are enforced from Zone B's `zone_b/contracts` registry as deterministic Python checks. `contract_checker.py` loads that registry and adds the operator-facing text. The verdict is pure code — never delegated to an LLM. Same trace, same violations, every time."**

28. **"Today all five contracts are enforced: evidence, tool, routing, approval, and schema. The fixture fails four of them and passes schema."**

29. **"Why this separation? A workflow can't grade its own homework. Zone A could lie in its narrative; Zone B reads the trace and catches the lie."**

---

## INPUT / OUTPUT (anticipated Q&A)

30. **"Input is one of two things. A `raw_trace` dict — an AG2-shaped trace JSON that skips Zone A and runs only the Zone B diagnostic. Or a `task_spec` dict — which drives Zone A end-to-end. Today `raw_trace` submission is fully wired; `task_spec` submission is schema-validated but requires Zone A runtime credentials to execute."**

31. **"Output is a Contract Violation Report — same dict shape regardless of input mode. Fourteen-plus fields including the violation list, severity summary, repair details, regression status, and an LLM-generated narrative."**

32. **"The dashboard renders that report via `window.CONCORD_DATA`. The API serves the same shape via `GET /api/runs/{run_id}` — the `api/adapter.py` module does the conversion."**

33. **(if asked about workflow submission)** **"Submit a run via `POST /api/runs` with `workflow_id` and `raw_trace`. The background task runs the full Zone B pipeline and updates the run status via SSE. Fetch the completed report with `GET /api/runs/{run_id}`."**

---

## INTEGRATIONS — REAL, NOT STUBBED

34. **"Tavily is live. `zone_a/agents/researcher.py` calls `TavilyClient.search` for every Zone A run, returns up to three sources, formats them with the LLM."**

35. **"Daytona is live. `zone_b/agents/regression_test.py` runs tests through `zone_b.sandbox.DaytonaExecutorPool`, backed by AG2's `DaytonaCodeExecutor`. It executes the generated Python block, parses stdout for PASS or FAIL, records duration/cost, and reports an explicit error if credentials are missing."**

36. **"LLM is Gemini 2.5 Flash via OpenRouter. Cheap, fast, structured-JSON friendly. Temperature 0.1 because we're parsing every response, not generating prose."**

---

## ZONE B — THE 7 AGENTS (memorize the chain)

37. **"TraceCollector — pure parsing, no LLM. Folds every `context_delta` left to right to build a final state snapshot."**

38. **"ContractChecker — three deterministic lambdas plus an LLM call only for the human-readable expected and observed strings."**

39. **"Attribution — LLM identifies the failed agent and root cause; deterministic fallback if the LLM response is unparseable."**

40. **"Repair — deterministic primitive map: evidence → Guardrail, tool → OnContextCondition, routing → Handoff, approval → HumanGate. LLM generates the patch_code snippet."**

41. **"RegressionTest — LLM writes a self-contained Python test, Daytona sandbox executes it, stdout is parsed for PASS or FAIL."**

42. **"Reporter — assembles the final report dict, LLM generates only the narrative paragraph."**

43. **"HumanGate — auto-approve in demo mode, real `UserProxyAgent` with stdin prompt in interactive mode."**

44. **"Sequential — not GroupChat. The pipeline is a deterministic DAG; round-robin GroupChat would just add LLM-driven routing on top of an already-deterministic flow."**

---

## ANTICIPATED Q&A — VERBATIM ANSWERS

**Q: Why deterministic lambdas for contracts instead of letting the LLM judge?**
45. **"Because contract verdicts have to be reproducible. If the same trace produces different violations on different runs, you can't trust the report. The LLM is only used to generate the human-readable expected and observed strings — never the pass/fail verdict."**

**Q: Why a separate Attribution agent?**
46. **"Because the agent whose contract failed is often downstream of the agent who caused the failure. Reporter emits final output without verified sources — Reporter's contract failed, but Verifier is responsible for `verified_sources_count = 0`. Attribution reasons over the handoff path to surface the upstream cause."**

**Q: Why keep a primary repair if repairs are per violation?**
47. **"The backend now emits one repair entry per violation, in trace order. We still keep a primary scalar repair for existing callers; it mirrors the highest-severity patch until the rest of the pipeline moves fully to the plural shape."**

**Q: What happens if the LLM returns garbage?**
48. **"Every Zone B agent has a deterministic fallback path. We never crash on a bad LLM turn — we mark `confidence=0.5` instead of `0.85` so the operator knows the patch is templated, not LLM-generated."**

**Q: Why Daytona instead of running tests locally or in a thread?**
49. **"LLM-generated code execution is inherently untrusted. Daytona gives per-run sandbox isolation with deterministic cleanup. Plus the sandbox image is reproducible — same `python:3.11-slim` every time, regardless of what's installed on the operator's machine."**

**Q: Is the dashboard wired to the live backend?**
50. **"Currently no — the live deploy uses an inline fixture so the demo can't fail on stage Wi-Fi. The `api/` directory has a working FastAPI adapter that converts a real Zone B report into the dashboard's `CONCORD_DATA` shape. It works locally; we held it off the live deploy for stage reliability."**

**Q: What AG2 primitives would a real operator install based on this report?**
51. **"Exactly the four shown on the Repair Patch screen — Guardrail with an evidence condition, ToolGate on the verifier's verdict function, OnContextCondition gating the Verifier→Reporter handoff, and UserProxyAgent with `human_input_mode='ALWAYS'` before any side-effect agent. These are AG2 framework primitives — they paste straight into the operator's existing code."**

**Q: How would you extend this beyond Literature Review?**
52. **"Zone B reads any trace JSON matching the shared models. Define your contracts in `zone_b/contracts` or register normalized YAML contracts through the API, then add your primitive map. The architecture is workflow-agnostic — Zone A is just our demo target."**

**Q: What's the track classification — Multi-Agent Collaboration or Open?**
53. **"Both fit. Concord is meta — it observes and repairs other multi-agent collaborations. We pitch it as multi-agent collaboration because that's what we're improving."**

---

## HONEST CONCESSIONS — say these BEFORE the judge catches them

54. **"All five contracts are enforced in code today. The current fixture passes schema, so the demo reports four violations rather than five."**

55. **"The backend emits four repair entries for the four fixture violations. The Repair screen's visual before/after diffs are still template-driven until the API passthrough work lands."**

56. **"The Workflow DAG topology block is fixture-first for the stage demo, and live mode can now render observed topology plus recurrence badges from persisted run history. Registered workflow declarations are also projected to FalkorDB when graph persistence is enabled."**

57. **"The Forensic screen — span tree, inspector, and deep-links — is queued in PRs #110-#113. It renders once those PRs land on production."**

58. **"Tavily, Daytona, and Gemini are real live integrations — not stubs. Without `DAYTONA_API_KEY` we return an explicit `(stdout='Daytona credentials missing', sandbox_id='no-sandbox', status='error')` — never a fake PASS."**

---

## CLOSER (last 15 seconds)

59. **"Concord Lite — declare your contracts in Zone A, get verdicts and AG2-native repairs from Zone B. Live demo at concord-lite.vercel.app, code at github.com/d3v07/AG2_Hackathon."**

60. **"Multi-agent systems fail silently. Concord makes them fail loudly — and tells you exactly which AG2 primitive fixes it."**

---

## EMERGENCY KEYBOARD SHORTCUTS

- **If live demo URL fails on stage:** `python run_all.py --fixture` produces the same report on stdout — fall back to that.
- **If REPLAY animation glitches:** click END STATE, walk through the static screens manually.
- **If asked "show me the API":** open `api/index.py` in the repo — point to `/api/health`, `/api/api-keys`, `/api/workflows`, `/api/runs`, `/api/runs/{id}/events`, and `/api/tenant/usage`.
- **If asked "show me the contracts":** open `zone_b/agents/contract_checker.py` lines 9-33 — that's the entire enforcement layer.
- **If asked "show me Daytona":** open `zone_b/agents/regression_test.py` lines 91-117 — `_run_in_daytona`.
- **If asked "show me the swarm":** open `zone_a/swarm.py` — point to `RoundRobinPattern`, `OnContextCondition`, `RegexGuardrail`, `register_handoffs`, `register_for_llm`.
- **If asked "show me task_spec submission":** the `RunCreate` schema in `api/schemas.py` accepts `task_spec`; the runtime check in `api/routes/runs.py:48-52` returns HTTP 400 until Zone A runtime wiring lands.
