# Concord AG2 Leverage Plan

## 1. Principle

Concord should use AG2 deeply but not recklessly.

The goal is not to name-drop every AG2 feature. The goal is to use AG2 where it makes the product more correct, inspectable, reliable, or faster to build.

Rule:

```text
Use AG2 primitives when they directly support contract checking, trace ingestion, repair generation, test validation, human approval, memory, or live UX.
```

## 2. P0 AG2 usage

| AG2 feature | Module path / import shape | Concord use | Decision |
|---|---|---|---|
| GroupChat | `from autogen import GroupChat, GroupChatManager` or current installed equivalent | Diagnostic multi-agent pipeline | Use |
| GroupChatManager | `from autogen import GroupChatManager` | Orchestrates diagnostic agents | Use |
| ConversableAgent | `from autogen import ConversableAgent` | Base class for diagnostic agents | Use |
| UserProxyAgent | `from autogen import UserProxyAgent` | Human approval gate | Use |
| ContextVariables | `from autogen.agentchat.group import ContextVariables` | Store workflow state, contract state, repair state | Use |
| OnContextCondition | `from autogen.agentchat.group import OnContextCondition` | Deterministic routing based on context variables | Use |
| Handoffs | `from autogen.agentchat.group.handoffs import Handoffs` | Production handoff repair patches | Use |
| RegexGuardrail | Verify exact installed import path | Citation/schema safety checks | Use |
| TavilySearchTool | `from autogen.tools.experimental import TavilySearchTool` | External evidence verification | Use |
| DaytonaCodeExecutor | `from autogen.coding import DaytonaCodeExecutor` | Run generated regression tests in sandbox | Use |
| LLMConfig | `from autogen import LLMConfig` | Gemini/OpenRouter/provider routing config | Use |
| AG2 OpenTelemetry | `from autogen.opentelemetry import instrument_agent, instrument_llm_wrapper, instrument_pattern` | Native trace ingestion | P1, but design now |

## 3. P1 AG2 usage

| AG2 feature | Module path / import shape | Concord use | Decision |
|---|---|---|---|
| AG-UI | `from autogen.ag_ui import AGUIStream` | Live dashboard streaming | Use if it fits dashboard event model |
| FalkorDB GraphRAG | `autogen.agentchat.contrib.graph_rag.falkor_graph_query_engine.FalkorGraphQueryEngine` and `autogen.agentchat.contrib.graph_rag.falkor_graph_rag_capability.FalkorGraphRagCapability` | Workflow topology graph and recurrence memory | Use |
| Mem0 | `from mem0 import Memory` | Long-term semantic memory of recurring violation patterns | Use if graph alone is not enough |
| Nested chats | `ConversableAgent.register_nested_chats(...)` | Repair -> Test -> Repair loop | Use after single-pass loop works |
| Custom speaker selection | `GroupChat(..., speaker_selection_method=callable)` | Skip unnecessary diagnostic stages | Use after baseline stability |
| DocAgent | `from autogen.agents.experimental import DocAgent` | Ingest design docs and draft contracts | Use after core contracts work |
| ReasoningAgent | `from autogen.agents.experimental import ReasoningAgent` | Complex multi-violation root-cause ranking | Use only for hard cases |

## 4. P2 / optional AG2 usage

| AG2 feature | Module path / import shape | Concord use | Decision |
|---|---|---|---|
| WebSurferAgent | `from autogen.agents.experimental import WebSurferAgent` | Browse external docs when contract references live pages | Optional |
| CaptainAgent | `from autogen.agentchat.contrib.captainagent import CaptainAgent` | Decide whether to invoke full diagnostics or assemble specialists | Not v1 core |
| AG2 Studio | Verify current integration path via official docs/repo | Visual import/export or contract visualization | Optional |
| A2A | `autogen.a2a.*` | Remote agent trust and Agent Passport later | Not v1 core |
| Twilio / RealtimeAgent | Current docs should be verified; avoid if deprecated | Voice approval | Avoid for v1 |
| AG2 GraphQL | Verify via docs before planning | Dashboard query layer | Do not plan until verified |

## 5. Code stubs

### 5.1 Diagnostic GroupChat

```python
from autogen import ConversableAgent, GroupChat, GroupChatManager, LLMConfig

llm_config = LLMConfig({
    "model": "gemini-2.5-flash",
    "api_key": "...",
    "api_type": "openai",
    "base_url": "https://openrouter.ai/api/v1",
    "temperature": 0.1,
})

trace_collector = ConversableAgent(
    name="TraceCollectorAgent",
    system_message="Normalize the run trace. Do not invent events.",
    llm_config=llm_config,
    human_input_mode="NEVER",
)

contract_checker = ConversableAgent(
    name="ContractCheckerAgent",
    system_message="Explain deterministic contract violations. Do not decide verdicts.",
    llm_config=llm_config,
    human_input_mode="NEVER",
)

repair_agent = ConversableAgent(
    name="RepairAgent",
    system_message="Map violations to AG2-native repair patches.",
    llm_config=llm_config,
    human_input_mode="NEVER",
)

group_chat = GroupChat(
    agents=[trace_collector, contract_checker, repair_agent],
    messages=[],
    max_round=8,
    speaker_selection_method="round_robin",
)

manager = GroupChatManager(groupchat=group_chat, llm_config=llm_config)
```

Use RoundRobin for deterministic v1 baseline. Add custom speaker selection later.

### 5.2 Handoffs repair pattern

```python
from autogen.agentchat.group.handoffs import Handoffs
from autogen.agentchat.group import OnContextCondition

# Pseudocode. Adjust target and condition classes to installed AG2 version.
verifier_agent.handoffs = (
    Handoffs()
    .add_context_condition(
        OnContextCondition(
            target=reporter_agent,
            condition=verified_sources_count_gt_zero_condition,
        )
    )
    .set_after_work(researcher_agent)
)
```

Concord should generate this as a suggested repair patch, not auto-apply it without approval.

### 5.3 Daytona regression test runner

```python
from autogen.coding import DaytonaCodeExecutor
from autogen import ConversableAgent


def run_generated_test_in_daytona(test_code: str) -> dict:
    with DaytonaCodeExecutor(timeout=60) as executor:
        code_executor_agent = ConversableAgent(
            name="daytona_test_executor",
            llm_config=False,
            code_execution_config={"executor": executor},
            human_input_mode="NEVER",
        )

        result = code_executor_agent.run(
            message=f"```python\n{test_code}\n```",
            max_turns=1,
        )
        return {
            "status": "completed",
            "summary": getattr(result, "summary", None),
        }
```

### 5.4 Tavily evidence tool

```python
from autogen.tools.experimental import TavilySearchTool

tavily_tool = TavilySearchTool(tavily_api_key=os.environ["TAVILY_API_KEY"])
```

A Tavily call must create a ToolEvent. Concord should flag claims that imply search if no corresponding ToolEvent exists.

### 5.5 AG2 native tracing adapter

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from autogen.opentelemetry import (
    instrument_agent,
    instrument_llm_wrapper,
    instrument_pattern,
)


def instrument_concord_workflow(agents, pattern=None):
    tracer_provider = TracerProvider()
    trace.set_tracer_provider(tracer_provider)

    instrument_llm_wrapper(tracer_provider=tracer_provider)

    for agent in agents:
        instrument_agent(agent, tracer_provider=tracer_provider)

    if pattern is not None:
        instrument_pattern(pattern, tracer_provider=tracer_provider)

    return tracer_provider
```

Build an exporter that maps AG2 spans into Concord TraceEvent.

### 5.6 FalkorDB GraphRAG

```python
from autogen.agentchat.contrib.graph_rag.falkor_graph_query_engine import FalkorGraphQueryEngine
from autogen.agentchat.contrib.graph_rag.falkor_graph_rag_capability import FalkorGraphRagCapability
from autogen import ConversableAgent

query_engine = FalkorGraphQueryEngine(
    name="concord_workflow_graph",
    host=os.environ.get("FALKORDB_HOST", "localhost"),
    port=int(os.environ.get("FALKORDB_PORT", "6379")),
)

graph_agent = ConversableAgent(
    name="ViolationMemoryAgent",
    human_input_mode="NEVER",
)

capability = FalkorGraphRagCapability(query_engine)
capability.add_to_agent(graph_agent)
```

Use direct graph operations for persistence. Use GraphRAG for querying and explanation.

### 5.7 Mem0 recurrence memory

```python
from mem0 import Memory

memory = Memory()


def remember_violation(tenant_id: str, workflow_id: str, violation_summary: str):
    memory.add(
        messages=[{"role": "system", "content": violation_summary}],
        user_id=f"{tenant_id}:{workflow_id}",
    )


def search_similar_violations(tenant_id: str, workflow_id: str, query: str):
    return memory.search(query, user_id=f"{tenant_id}:{workflow_id}")
```

Use Mem0 for semantic recurrence. Use FalkorDB for exact topology and contract relationships.

### 5.8 DocAgent contract drafting

```python
from autogen.agents.experimental import DocAgent

doc_agent = DocAgent(
    name="WorkflowIntentDocAgent",
    llm_config=llm_config,
    parsed_docs_path="./data/parsed_docs",
    collection_name="workflow_intent_docs",
)
```

Use case:

```text
operator uploads workflow design doc
  -> DocAgent extracts intended behavior
  -> Concord proposes draft contracts
  -> human approves contracts
```

### 5.9 ReasoningAgent for hard cases

```python
from autogen.agents.experimental import ReasoningAgent

reasoning_agent = ReasoningAgent(
    name="ComplexRootCauseAgent",
    llm_config=llm_config,
    grader_llm_config=llm_config,
    max_depth=3,
    beam_size=3,
)
```

Use only for multi-violation cases where deterministic checks find several possible root causes.

### 5.10 WebSurferAgent

```python
from autogen.agents.experimental import WebSurferAgent

websurfer = WebSurferAgent(
    name="ExternalDocsAgent",
    web_tool="crawl4ai",
    llm_config=llm_config,
)
```

Use only when a contract references external documentation that Tavily cannot cover cleanly.

### 5.11 Nested chat for repair-test iteration

```python
repair_loop = [
    {
        "recipient": repair_agent,
        "message": "Generate a minimal repair patch for the violation.",
        "max_turns": 1,
        "summary_method": "last_msg",
    },
    {
        "recipient": regression_test_agent,
        "message": "Generate and evaluate a regression test for the repair.",
        "max_turns": 1,
        "summary_method": "last_msg",
    },
]

repair_supervisor.register_nested_chats(
    chat_queue=repair_loop,
    trigger=lambda sender: True,
)
```

Use after single-pass repair generation is stable.

### 5.12 Custom speaker selection

```python
def diagnostic_speaker_selection(last_speaker, groupchat):
    state = extract_state(groupchat.messages)

    if state.get("violation_count") == 0:
        return reporter_agent

    if state.get("violation_count") == 1 and not state.get("needs_complex_attribution"):
        return repair_agent

    if state.get("test_failed"):
        return repair_agent

    return "round_robin"
```

Use only after deterministic baseline is stable.

### 5.13 CaptainAgent

```python
from autogen.agentchat.contrib.captainagent import CaptainAgent

captain = CaptainAgent(
    name="ConcordCaptain",
    llm_config=llm_config,
)
```

Possible use:

- decide whether to run full diagnostics
- assemble specialized agents for unknown contract types
- recommend contract pack

Decision:

- Not v1 core.
- Too much autonomy before contracts are stable.

### 5.14 Per-provider LLM routing

```python
from autogen import LLMConfig

fast_config = LLMConfig({
    "model": "gemini-2.5-flash",
    "api_key": os.environ["OPENROUTER_API_KEY"],
    "api_type": "openai",
    "base_url": "https://openrouter.ai/api/v1",
    "temperature": 0.1,
})

strong_config = LLMConfig({
    "model": "gemini-2.5-pro",
    "api_key": os.environ["GEMINI_API_KEY"],
    "api_type": "gemini",
    "temperature": 0.1,
})
```

Policy:

```text
cheap deterministic explanations -> Gemini Flash
complex repair ranking -> Gemini Pro or stronger model
fallback -> configured secondary provider
```

Track model selection and cost per run.

## 6. AG2 features to avoid for now

| Feature | Why avoid |
|---|---|
| Random speaker selection | Bad for correctness product |
| Fully autonomous repair application | Too risky |
| CaptainAgent in core path | Too much dynamic behavior before contracts are stable |
| WebSurfer for basic search | Tavily is simpler and more reliable |
| Twilio RealtimeAgent | Verify current support before building; not needed for v1 |
| AG2 GraphQL | Not verified in official docs during planning |
| Full AG2 Studio dependency | Useful later, not production core |

## 7. Recommended AG2 sequencing

### Now

1. Stabilize deterministic contract engine.
2. Use existing AG2 GroupChat.
3. Use Daytona and Tavily visibly.
4. Keep UserProxyAgent approval.

### Next

1. Add native AG2 OpenTelemetry ingestion.
2. Add SDK one-line instrumentation.
3. Add live dashboard streaming.
4. Add persistent workflow/run storage.

### Then

1. Add FalkorDB topology and recurrence memory.
2. Add nested repair-test iteration.
3. Add DocAgent contract drafting.
4. Add custom speaker selection.
5. Add Mem0 if semantic recurrence needs it.

### Later

1. AG2 Studio import/export.
2. A2A remote-agent trust.
3. LangGraph adapter.
4. Contract marketplace.
