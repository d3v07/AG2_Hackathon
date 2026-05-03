import asyncio
import json
from pathlib import Path
from zone_b.agents.trace_collector import run_trace_collector
from zone_b.agents.contract_checker import run_contract_checker


async def main():
    raw = json.loads(Path("zone_b/fixtures/sample_trace.json").read_text())

    collected = await run_trace_collector(raw)
    print(f"Trace: {collected['summary']}")

    checked = await run_contract_checker(collected["run_trace"], collected["context_snapshot"])
    print(f"\nViolations found: {checked['violation_count']}")
    for v in checked["violations"]:
        print(f"  [{v.severity.upper()}] {v.contract_type}: {v.rule}")
        print(f"    expected : {v.expected}")
        print(f"    observed : {v.observed}")


if __name__ == "__main__":
    asyncio.run(main())
