# Concord SDK

The SDK wires AG2 tracing into Concord's existing raw-trace API.

```python
from concord_sdk import instrument

session = instrument(
    workflow_agents,
    api_url="http://localhost:8765",
    api_key="",
    workflow_id="WF-12345678",
)

session.complete(run_trace)
```

`run_trace` is the same dictionary shape written by `zone_a.trace_emitter`:

```python
{
    "run_id": "run_001",
    "workflow_name": "LiteratureReviewAssistant",
    "events": [...],
    "final_output": {...},
}
```

For local demo runs before keys are configured, Concord accepts the `local`
tenant without a key. For tenant-scoped runs, pass both `tenant_id` and
`api_key`; the client sends a bearer token plus tenant headers.

```python
session = instrument(
    workflow_agents,
    api_url="https://concord.example",
    api_key="tenant-secret",
    tenant_id="tenant-a",
)
```

Install locally from the repository root:

```bash
python3 -m pip install -e ./sdk
```
