"""
run_all.py — Full pipeline: Zone A → Zone B

Modes:
    python run_all.py                       # legacy sequential pipeline
    python run_all.py --fixture             # skip Zone A, use existing trace
    python run_all.py --swarm               # AG2 RoundRobinPattern (Zone A + Zone B)
    python run_all.py --swarm --fixture     # only run Zone B as a GroupChat
    python run_all.py --swarm --interactive # AG2 swarm with real human gate
"""
import argparse
import asyncio
import sys
from pathlib import Path


TRACE_PATH = "zone_b/fixtures/sample_trace.json"


def _run_zone_a_legacy() -> None:
    """Sequential pipeline — generates the historical 5-event broken trace."""
    from zone_a.run import run
    run()


async def _run_zone_a_swarm(interactive: bool) -> dict:
    """AG2 RoundRobinPattern swarm with OnContextCondition handoffs + guardrails."""
    from zone_a.swarm import run_swarm
    return await run_swarm(interactive=interactive)


async def _run_zone_b_legacy(trace_path: str) -> dict:
    """Sequential async pipeline — what the existing tests target."""
    from zone_b.orchestrator import run_diagnostic_pipeline
    return await run_diagnostic_pipeline(trace_path)


async def _run_zone_b_group_chat(trace_path: str, interactive: bool) -> dict:
    """AG2 RoundRobinPattern over the 7 diagnostic stages."""
    from zone_b.group_chat import run_diagnostic_group_chat
    return await run_diagnostic_group_chat(trace_path, interactive=interactive)


def _print_report(report: dict) -> None:
    width = 60
    print("\n" + "=" * width)
    print("  CONTRACT VIOLATION REPORT")
    print("=" * width)
    print(f"  Run ID            : {report.get('run_id', '<unknown>')}")
    print(f"  Workflow          : {report.get('workflow_name', '<unknown>')}")
    print(f"  Violations        : {report.get('violation_count', 0)}")
    print(f"  Severity          : {report.get('severity_summary', {})}")
    print(
        f"  Failed agent      : {report.get('failed_agent', '<unknown>')} "
        f"(step {report.get('failed_step', '?')})"
    )
    print(f"  Root cause        : {report.get('likely_root_cause', '<unknown>')}")
    print(f"  Affected primitive: {report.get('affected_primitive', '<unknown>')}")
    print(f"  Repair patch      : {report.get('repair_patch', '<unknown>')}")
    print(f"  Repair confidence : {report.get('repair_confidence', 0):.2f}")
    print(f"  Regression status : {report.get('regression_test_status', '<unknown>')}")
    print(f"  Approval status   : {report.get('approval_status', '<unknown>')}")
    narrative = report.get("narrative", "")
    print(
        f"\n  Narrative:\n  {narrative.replace(chr(10), chr(10) + '  ')}"
    )
    print("=" * width)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full Zone A + Zone B pipeline."
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Skip Zone A and use the existing zone_b/fixtures/sample_trace.json",
    )
    parser.add_argument(
        "--swarm",
        action="store_true",
        help="Use AG2 RoundRobinPattern (Zone A swarm + Zone B group chat)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enable real human input at HumanGate via UserProxyAgent",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  CONCORD LITE — Full Pipeline Run")
    if args.swarm:
        print("  Mode: AG2 swarm + group chat")
    elif args.fixture:
        print("  Mode: legacy (fixture)")
    else:
        print("  Mode: legacy (live)")
    print("=" * 60)

    if args.fixture:
        if not Path(TRACE_PATH).exists():
            print(f"\n  ERROR: {TRACE_PATH} not found. Run without --fixture first.")
            sys.exit(1)
        print(f"\n[Zone A] Skipped — using fixture trace at {TRACE_PATH}")
    else:
        print("\n[Zone A] Running...")
        try:
            if args.swarm:
                asyncio.run(_run_zone_a_swarm(interactive=args.interactive))
            else:
                _run_zone_a_legacy()
        except EnvironmentError as e:
            print(f"  ERROR: {e}")
            print("  Tip: run with --fixture to use the existing trace without API keys.")
            sys.exit(1)
        except Exception as e:
            print(f"  Zone A error: {e}")
            sys.exit(1)

    print("\n[Zone B] Running diagnostic pipeline...")
    try:
        if args.swarm:
            report = asyncio.run(
                _run_zone_b_group_chat(TRACE_PATH, interactive=args.interactive)
            )
        else:
            report = asyncio.run(_run_zone_b_legacy(TRACE_PATH))
    except Exception as e:
        print(f"  Zone B pipeline error: {e}")
        sys.exit(1)

    _print_report(report)


if __name__ == "__main__":
    main()
