# Codex Handoff — Concord v1.0 Execution

You are Codex (or any subsequent AI coding agent) picking up work on Concord v1.0. This document is self-contained: read it before touching anything. Do not skip the pre-flight checks.

---

## 1. The mission

Concord Lite was a hackathon prototype that won. Concord v1.0 turns it into a real AG2-first contract-to-repair platform: developers register multi-agent workflows, submit traces, get deterministic contract violations, per-violation repair patches, Daytona-validated regression tests, and persistent run history. AG2-first; not LangGraph, not generic observability, not a no-code builder.

Core sentence:

> Concord reads a multi-agent workflow trace plus its workflow contract, detects contract violations, maps each violation to the broken AG2 primitive, generates a repair patch, validates it with a regression test, and stores the learning so the same failure does not return.

---

## 2. Pre-flight checks (BEFORE any change)

Run these in order. Stop at the first failure and surface it; do not continue.

```bash
# 1. Confirm branch + remote state
git branch --show-current               # expect: production OR a feat/sprint-N branch
git status --short                      # working tree should be clean OR show only your intended changes
git fetch origin
git log origin/main..HEAD --oneline     # what's local-only
git log HEAD..origin/main --oneline     # what's on remote you don't have

# 2. Confirm you can run the existing system
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -e .                         # or: pip install -r requirements.txt
pytest -x --tb=short                     # all collected tests must pass before you touch anything
python run_all.py --fixture              # full pipeline must produce a Contract Violation Report on stdout

# 3. Confirm the live demo still works
curl -s -o /dev/null -w "%{http_code}\n" https://concord-lite.vercel.app/   # expect 200

# 4. Read the four reference docs (mandatory)
docs/ARCHITECTURE.md          # what's built today (file:line refs)
docs/QA_DEEP.md               # 70 grounded Q&A
docs/PLAN_VS_REALITY.md       # what's missing vs the original plan
docs/DEMO_SCRIPT.md           # what the demo path looks like

# 5. Read the v1.0 plan + AG2 leverage map
concord_v1_artifacts/CLAUDE_EXECUTION_PROMPT_CONCORD_V1.md
concord_v1_artifacts/docs/CONCORD_PRD.md
concord_v1_artifacts/docs/CONCORD_AG2_LEVERAGE.md
concord_v1_artifacts/docs/CONCORD_REAL_PRODUCT.md
```

If any of those steps fail, **stop and ask the user**. Do not "fix" pre-existing failures as part of your first commit.

---

## 3. The work — 30 issues across 10 sprints

All issues live on https://github.com/d3v07/AG2_Hackathon/issues, assigned to `d3v07`.

```
Sprint  3   #12, #13, #14   Foundation: close v0 gaps (audit + Routing + Schema contract lambdas)
Sprint  4   #15, #16, #17   Per-violation repair + test
Sprint  5   #18, #19, #20   SQLite persistence + workflow/run registration
Sprint  6   #21, #22, #23   Native AG2 OTel tracing + concord-sdk
Sprint  7   #24, #25, #26   Live dashboard streaming (SSE)
Sprint  8   #27, #28, #29   Real Daytona repair-test-iterate loop
Sprint  9   #30, #31, #32   FalkorDB topology + violation memory
Sprint 10   #33, #34, #35   Contract DSL (YAML)
Sprint 11   #36, #37, #38   Tenant + auth + cost dashboard
Sprint 12   #39, #40, #41   Deployment (Docker, CI, hosted backend)
```

**Strict ordering.** Sprint N depends on Sprint N-1 unless an issue body says otherwise. Within a sprint, issues are numbered in execution order; respect the `Depends on` field in each issue body.

Start with **#12** (audit doc). It blocks #13 and #14.

---

## 4. The workflow per sprint (test → ship → test → ship)

Repeat this loop for every sprint, every issue inside the sprint:

```
1. git checkout main && git pull origin main
2. git checkout -b feat/sprint-N-<short-name>           # new branch per sprint
3. For each issue in the sprint, in dependency order:
     a. Read the issue body. Restate the goal in your own words.
     b. RED — write the failing test first (tests/test_*.py)
     c. Run the test, confirm it fails for the RIGHT reason
     d. GREEN — write the minimal implementation
     e. Run the test, confirm it passes
     f. Run the full suite — pytest -x. Must stay green.
     g. Lint — ruff check . (or whatever the project uses)
     h. Commit:
          git add <files>
          git commit -m "feat: <description> (Closes #N)"
        — NEVER use --no-verify
        — NEVER mention AI, Claude, Codex, Anthropic, OpenAI in commit messages
        — Reference the closed issue number with "Closes #N"
4. After all issues in the sprint complete:
     a. git push origin feat/sprint-N-<short-name>
     b. gh pr create --title "Sprint N: <name>" --body "<see template below>"
     c. SELF-REVIEW the diff line by line. Verify against acceptance criteria.
     d. Run /review skill if available, otherwise re-run the full verification:
          pytest -x --tb=short
          ruff check .
          python run_all.py --fixture          # smoke test the full pipeline
          curl /api/health if API affected
     e. Report results in PR comment (test count, coverage delta, screenshot if UI changed).
5. STOP and ask the user before merging. Do not auto-merge to main.
6. After user approves merge:
     a. gh pr merge --squash <PR#>             # squash if commit history is noisy
     b. git checkout main && git pull
     c. Loop to next sprint.
```

### PR body template

```markdown
## Summary
- <bullet 1>
- <bullet 2>
- <bullet 3>

## Issues Closed
- Closes #X — <title>
- Closes #Y — <title>

## Verification
- Build: OK / FAIL
- Tests: A/B passed (C% coverage, +/-D vs main)
- Lint: OK / X issues
- Smoke: `python run_all.py --fixture` produces report ✅
- API health: 200 ✅ (if applicable)

## Test Plan
- [ ] <scenario 1>
- [ ] <scenario 2>
- [ ] <scenario 3>

## Screenshots / Evidence
<paste if UI changed>
```

---

## 5. Coding principles (non-negotiable)

These come from the project owner's `CLAUDE.md`. Violations will be reverted.

### Priority order
**SOLID, DRY, KISS, YAGNI** — in that order. When YAGNI conflicts with SOLID, YAGNI wins.

### What to do
- Read files before modifying them. Never edit blind.
- Search the codebase for existing patterns first. Reuse before inventing.
- Vertical slices over horizontal layers. One complete user-visible path before starting the next.
- Make every change reversible. Small commits. Reference issues.
- Keep the demo path working. `python run_all.py --fixture` must pass after every commit.
- Determinism wins. Contract verdicts are pure code. LLMs may explain, never decide.
- Every LLM call needs a deterministic fallback path.
- Files: 200-400 lines typical, 800 max. Functions: < 50 lines, no nesting > 4 levels.
- Add tests with every feature. No bulk-dropping untested code.

### What NOT to do
- **NEVER mention AI, Claude, Codex, Anthropic, OpenAI in commits, comments, code, or PR titles.** Not even "Co-Authored-By". Not even "Generated by". Nothing.
- NEVER use `--no-verify` on git commits.
- NEVER force-push to `main` or `master`. Even if asked, warn first.
- NEVER push secrets. Check `.env` is gitignored before every push. Run truffleHog if available.
- NEVER add comments unless the WHY is non-obvious (one line max).
- NEVER add docstrings to untouched code.
- NEVER write code that does what the function name already says.
- NEVER add backwards-compat shims, mocks, or placeholder code in production paths.
- NEVER scaffold "everything first, wire later". Wire and test one path before moving on.
- NEVER add error handling for impossible scenarios. Validate at system boundaries only.
- NEVER use marketing language ("blazingly fast", "robust", "comprehensive").
- NEVER add emoji to code or commits unless explicitly requested.
- NEVER use --force on `git push`. Use `+refspec` only when explicitly authorized AND the user said "force-push" in plain words.

### Push permission rule (critical, learned the hard way)
**Push permission is per-action, not standing.** If the user said "push to GitHub" once, that authorized THAT push only. Every subsequent push needs fresh explicit authorization. Even doc-only commits. Don't extrapolate.

If you wrote code, ran tests, and it's all green: ask "Want me to push?" before pushing. One sentence is enough.

---

## 6. Pre-push checklist (every push)

Run through this list every single time before `git push`. If any item fails or feels uncertain, STOP and ask the user.

- [ ] All tests pass: `pytest -x --tb=short`
- [ ] Lint clean: `ruff check .`
- [ ] No console.log / print debug statements in production code
- [ ] No secrets staged: `git diff --cached | grep -iE "(api[_-]?key|secret|token|password)" || echo OK`
- [ ] `.env` in `.gitignore`: `git check-ignore .env && echo OK`
- [ ] Commit message has no AI references: `git log -1 | grep -iE "(claude|codex|anthropic|openai|copilot|ai|gpt)" || echo OK`
- [ ] Branch is correct (not main, not production for v1.0 work — use `feat/sprint-N-*`)
- [ ] No uncommitted changes that should have been included
- [ ] User explicitly authorized the push for this action (not extrapolated from earlier)

If pushing a PR:
- [ ] PR body filled in (summary, issues closed, verification, test plan)
- [ ] Self-review done — read the diff line by line
- [ ] No "TODO" or "FIXME" left for core logic
- [ ] Demo path still works: `python run_all.py --fixture`

---

## 7. Verification gates (between sprints)

Between Sprint N's PR merge and Sprint N+1's first commit, run a full verification pass:

```bash
pytest -x --tb=short                      # all green
ruff check .                              # clean
python run_all.py --fixture               # full pipeline produces Contract Violation Report
curl -s https://concord-lite.vercel.app/  # 200 + dashboard renders
```

If anything is broken, fix it on `main` directly (small fix commit, mention in PR description) before starting the next sprint. Do not start Sprint N+1 with broken `main`.

---

## 8. AG2 specifics — what to use, what to avoid

This is condensed from `concord_v1_artifacts/docs/CONCORD_AG2_LEVERAGE.md`. Read that doc for code stubs.

### Use (P0)
| Feature | Module |
|---|---|
| `ConversableAgent`, `UserProxyAgent`, `GroupChat`, `GroupChatManager` | `autogen` |
| `ContextVariables`, `OnContextCondition` | `autogen.agentchat.group` |
| `Handoffs` | `autogen.agentchat.group.handoffs` |
| `RegexGuardrail` | verify import path before use |
| `TavilySearchTool` | `autogen.tools.experimental` |
| `DaytonaCodeExecutor` | `autogen.coding` |
| `LLMConfig` | `autogen` |

### Use (P1, in-sprint planning)
| Feature | Module | When |
|---|---|---|
| AG2 OpenTelemetry instrumentation | `autogen.opentelemetry.{instrument_agent, instrument_llm_wrapper, instrument_pattern}` | Sprint 6 |
| `register_nested_chats` | `autogen.ConversableAgent` | Sprint 8 (Repair-Test-Iterate) |
| FalkorDB GraphRAG | `autogen.agentchat.contrib.graph_rag.falkor_graph_query_engine.FalkorGraphQueryEngine` | Sprint 9 |

### Avoid (P2 or never in v1.0)
- Random speaker selection — bad for a correctness product
- Fully autonomous repair application — too risky; HumanGate stays mandatory
- `CaptainAgent` in core path — too much autonomy before contracts are stable
- WebSurferAgent for basic search — Tavily is simpler
- Twilio voice — verify support, but not v1.0
- AG2 GraphQL — unverified in docs, do not plan around it

### Verify-before-use
For any AG2 feature: confirm the actual import path in the installed AG2 version before writing code that depends on it. The plan calls for "verify via docs" disclaimers. Honor them.

```bash
python -c "from autogen.opentelemetry import instrument_agent; print('OK')" 2>&1 | head -1
```

If it fails, document the actual path in `docs/AG2_VERSIONING.md` and use what works.

---

## 9. What's already live (do not rebuild)

These work today. Don't replace them; integrate around them.

- Zone A target workflow (Literature Review Assistant) — `zone_a/run.py`, `zone_a/swarm.py`
- Zone B 7-agent diagnostic pipeline — `zone_b/orchestrator.py`, `zone_b/agents/*.py`
- Tavily live integration — `zone_a/agents/researcher.py:46-58`
- Daytona live integration — `zone_b/agents/regression_test.py:98-123`
- Gemini 2.5 Flash via OpenRouter — `zone_a/config.py:7-17`
- 5 of 5 deterministic contracts (Evidence, Tool, Routing, Approval, Schema) — `zone_b/agents/contract_checker.py:9-88`
- AG2 swarm with `OnContextCondition` + `RegexGuardrail` runtime enforcement — `zone_a/swarm.py:201-231`
- 288 unit + integration tests — `tests/`
- Static dashboard on Vercel (fixture-driven) — `public/index.html`, https://concord-lite.vercel.app/
- Local FastAPI + adapter — `api/index.py`, `api/adapter.py`, `api/store.py`
- Three reference docs — `docs/ARCHITECTURE.md`, `docs/DEMO_SCRIPT.md`, `docs/QA_DEEP.md`

---

## 10. What's intentionally NOT in v1.0

From the PRD non-goals — push back if anyone asks for these in a v1.0 sprint:

- LangGraph / CrewAI / OpenAI Agents SDK adapters
- No-code workflow builder
- Full LangSmith / AgentOps replacement
- Twilio voice approval
- AG2 GraphQL (unverified)
- A2A remote-agent trust
- Contract pack marketplace
- Fully autonomous patch application

These are Concord Platform (post-v1.0) territory.

---

## 11. Communication protocol with the user

- Before substantive work: confirm interpretation. "I'm going to implement #X by doing Y. OK?"
- After every test pass: short status. One sentence.
- After every commit: list files changed + line counts.
- Before any push: explicit ask. "Ready to push to feat/sprint-N-foo?"
- Before any PR merge: explicit ask. "PR ready for merge?"
- If stuck for more than 30 minutes on the same problem: STOP, summarize what you tried, ask.
- If user gives feedback ("don't do that again"): save it. Treat as a durable rule for the rest of the session.

---

## 12. Failure modes — what to do when things go wrong

- **Tests fail after your change**: revert your change, narrow the diff, retry. Do not commit broken tests.
- **Pre-existing tests fail before your change**: stop. Surface to user. Do not start your work on a broken baseline.
- **Daytona credentials missing**: pipeline returns `regression_test_status="error"` honestly. Don't fake PASS.
- **Tavily key missing**: Zone A raises `EnvironmentError`. Use `--fixture` mode.
- **OpenRouter rate-limited**: every Zone B agent has deterministic fallback. Pipeline still completes with `confidence=0.5` instead of 0.85.
- **AG2 import path differs from spec**: document the actual path, use what works, mention in PR.
- **Force-push needed**: stop. Ask user. Never decide unilaterally.
- **Merge conflict on main**: rebase your branch, resolve manually. Never just `--theirs` or `--ours` without reading.

---

## 13. Where to find context

| Need | File |
|---|---|
| What was built and why | `docs/ARCHITECTURE.md` |
| Likely judge / user questions with answers | `docs/QA_DEEP.md` |
| Northstar plan vs reality scorecard | `docs/PLAN_VS_REALITY.md` |
| Demo script for live presentations | `docs/DEMO_SCRIPT.md` |
| v1.0 PRD | `concord_v1_artifacts/docs/CONCORD_PRD.md` |
| v1.0 architecture | `concord_v1_artifacts/docs/CONCORD_ARCHITECTURE.md` |
| AG2 leverage plan with code stubs | `concord_v1_artifacts/docs/CONCORD_AG2_LEVERAGE.md` |
| The original ChatGPT execution prompt | `concord_v1_artifacts/CLAUDE_EXECUTION_PROMPT_CONCORD_V1.md` |
| Source URLs for AG2 docs | `concord_v1_artifacts/docs/SOURCES.md` |
| Concord Lite README + demo path | `README.md` |

---

## 14. The first thing to do

After running every step in section 2 and confirming green:

1. Read `concord_v1_artifacts/CLAUDE_EXECUTION_PROMPT_CONCORD_V1.md` end to end.
2. Read issue #12 on GitHub.
3. Restate #12's goal back to the user in your own words.
4. Wait for confirmation.
5. Branch: `git checkout -b feat/sprint-3-foundation`.
6. Begin TDD on #12 (write the audit doc).

Do not start anything until step 4 returns explicit approval.
