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

### Screen 1 — Overview
8. **"This is Zone B's report rendered on top of Zone A's execution. The 5 agents you see ARE Zone A — Researcher, Critic, Verifier, Reporter, Action. Zone B added the violation count, the contract status table, and the severity breakdown."**

9. **(click REPLAY RUN)** **"This is the recorded trace playing back. Twelve events, ~520 milliseconds per step. Researcher and Critic pass. Verifier turns red — that's where the contract failure happens. Reporter and Action both fail downstream."**

10. **"Bottom-right of each agent: the per-agent footer. 'no tool_event' under Verifier, 'verified=0' under Reporter, 'approval=pending' under Action. These are the failures we'll trace through the rest of the demo."**

### Screen 2 — Workflow DAG
11. **(click 02 Workflow DAG)** **"This is the declared topology versus the observed path. Eight nodes — five agents, the GroupChat manager, the Tavily tool, and a proposed HumanGate that doesn't exist in the original program."**

12. **"Color-coded edges. Sage means OK. Orange means SKIPPED GUARD — the handoff from Verifier to Reporter fired without satisfying its precondition. Red means MISSING APPROVAL — Reporter handed off to Action with `approval_status=pending`. Gold dashed is PROPOSED — that's the HumanGate Concord wants to add."**

13. **"Routing violations are structural — you can see them in the graph before you read the contract definitions."**

### Screen 3 — Agent Trace
14. **(click 03 Agent Trace)** **"Twelve events from the trace JSON. Each row is one TraceEvent — step number, timestamp, agent, event type, context delta, status. The flagged rows show which contract tripped."**

15. **"Step 8: Verifier says 'I verified the key claims' — flagged C-TOL because there's no matching tool event. Step 9: Verifier writes verified_sources_count=0 — flagged C-EVD. Step 12: Action runs save_report with approval_status=pending — flagged C-APR."**

### Screen 4 — Violations
16. **(click 04 Violations)** **"Four violations, three HIGH severity, one MED. Each card has the contract that failed, what was expected, what was observed, the failed agent, and an evidence chain pointing back to the trace steps."**

17. **(click any violation row)** **"Clicking a violation jumps you straight to the proposed repair patch — that's the operator workflow."**

### Screen 5 — Repair Patch
18. **"Four AG2-native primitive patches. Guardrail, ToolGate, OnContextCondition, and UserProxyAgent slash HumanGate. Each one shows before / after — red lines are removed, green lines are added."**

19. **"These aren't pseudo-code. The added lines paste straight into the operator's `ConversableAgent(...)` constructor or `Handoffs(...)` call. The repair targets the AG2 framework primitive, not the user's business logic."**

20. **"P-001 adds a Guardrail to Reporter — `condition=lambda ctx: ctx['verified_sources_count'] > 0`. P-002 wraps Verifier's `emit_verdict` in a tool-event check. P-003 gates the Verifier→Reporter handoff with `OnContextCondition`. P-004 inserts a UserProxyAgent with `human_input_mode='ALWAYS'` before Action."**

### Screen 6 — Regression
21. **(click 06 Regression)** **"This is the Daytona sandbox. Per-run isolation, fresh `python:3.11-slim` image, sandbox ID `dt-9f3a-2b71`. The terminal stream is captured stdout from `sandbox.process.code_run`."**

22. **"Four assertions, all PASS. The LLM generated the test code. Daytona executed it. We always delete the sandbox in `finally` — no resource leak, no cleanup burden on the operator."**

23. **"This is where Daytona earns its keep. We're executing LLM-generated code — running that on the operator's machine is unsafe."**

### Screen 7 — Final Report
24. **(click 07 Final Report)** **"Notice the top-right status flipped from '4 VIOLATIONS DETECTED' in red to 'RERUN READY' in green. That's the explicit signal the loop is closed."**

25. **"Executive summary is LLM-generated narrative. Approval block shows PENDING_OPERATOR — in interactive mode that triggers a real `UserProxyAgent` prompt. Patches Applied table is the deterministic part — four AG2 primitives mapped to four contract types."**

---

## CONTRACTS — WHERE THEY LIVE (must-know, very likely Q&A)

26. **"Contracts are declared in Zone A's `workflow_contract.py` as a plain manifest — five rules with IDs C1 through C5, types, and severities. That's the workflow author's promise."**

27. **"Contracts are enforced in Zone B's `contract_checker.py` as deterministic Python lambdas. The verdict is pure code — never delegated to an LLM. Same trace, same violations, every time."**

28. **"Today all five contracts are enforced: evidence, tool, routing, approval, and schema. The fixture fails four of them and passes schema."**

29. **"Why this separation? A workflow can't grade its own homework. Zone A could lie in its narrative; Zone B reads the trace and catches the lie."**

---

## INPUT / OUTPUT (anticipated Q&A)

30. **"Input is one of two things. Either a research task in `zone_a/fixtures/task.json` — that drives the full Zone A then Zone B pipeline. Or an existing AG2-shaped trace JSON — that skips Zone A and runs only the Zone B diagnostic."**

31. **"Output is a Contract Violation Report — same dict shape regardless of input mode. Fourteen fields including the violation list, severity summary, repair details, regression status, and an LLM-generated narrative."**

32. **"The dashboard renders that report via `window.CONCORD_DATA`. The API serves the same shape via `GET /api/runs/{run_id}` — the `api/adapter.py` module does the conversion."**

33. **(if asked about workflow submission)** **"Workflow submission is an API contract. `GET /api/runs/{run_id}` returns the report. The submission endpoint — `POST /api/runs` — is the obvious next layer; the adapter that would feed it is already in `api/adapter.py`."**

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
52. **"Zone B reads any trace JSON matching the shared models. Define your own contracts as lambdas in the CONTRACTS list and your own primitive map. The architecture is workflow-agnostic — Zone A is just our demo target."**

**Q: What's the track classification — Multi-Agent Collaboration or Open?**
53. **"Both fit. Concord is meta — it observes and repairs other multi-agent collaborations. We pitch it as multi-agent collaboration because that's what we're improving."**

---

## HONEST CONCESSIONS — say these BEFORE the judge catches them

54. **"All five contracts are enforced in code today. The current fixture passes schema, so the demo reports four violations rather than five."**

55. **"The backend emits four repair entries for the four fixture violations. The Repair screen's visual before/after diffs are still template-driven until the API passthrough work lands."**

56. **"The Workflow DAG topology block is fixture-first for the stage demo, and live mode can now render observed topology plus recurrence badges from persisted run history. Registered workflow declarations are also projected to FalkorDB when graph persistence is enabled."**

57. **"Tavily, Daytona, and Gemini are real live integrations — not stubs. Without `DAYTONA_API_KEY` we return an explicit `(stdout='Daytona credentials missing', sandbox_id='no-sandbox', status='error')` — never a fake PASS."**

---

## CLOSER (last 15 seconds)

58. **"Concord Lite — declare your contracts in Zone A, get verdicts and AG2-native repairs from Zone B. Live demo at concord-lite.vercel.app, code at github.com/d3v07/AG2_Hackathon."**

59. **"Multi-agent systems fail silently. Concord makes them fail loudly — and tells you exactly which AG2 primitive fixes it."**

---

## EMERGENCY KEYBOARD SHORTCUTS

- **If live demo URL fails on stage:** `python run_all.py --fixture` produces the same report on stdout — fall back to that.
- **If REPLAY animation glitches:** click END STATE, walk through the static screens manually.
- **If asked "show me the API":** open `api/index.py` in the repo — point to the four endpoints (`/api/health`, `/api/runs`, `/api/runs/{id}`, `/api/runs/{id}/approval`).
- **If asked "show me the contracts":** open `zone_b/agents/contract_checker.py` lines 9-33 — that's the entire enforcement layer.
- **If asked "show me Daytona":** open `zone_b/agents/regression_test.py` lines 91-117 — `_run_in_daytona`.
