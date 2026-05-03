"""
run_all.py — Full pipeline: Zone A → Zone B

Usage:
    python run_all.py            # live run (requires TAVILY_API_KEY + OPENROUTER_API_KEY)
    python run_all.py --fixture  # use existing zone_b/fixtures/sample_trace.json, skip Zone A
"""
import argparse
import asyncio
import sys
from pathlib import Path


TRACE_PATH = "zone_b/fixtures/sample_trace.json"


def _run_zone_a() -> None:
    """Run Zone A pipeline — generates zone_b/fixtures/sample_trace.json."""
    from zone_a.run import run
    run()


async def _run_zone_b(trace_path: str) -> dict:
    """Run Zone B diagnostic pipeline on the given trace file."""
    from zone_b.orchestrator import run_diagnostic_pipeline
    return await run_diagnostic_pipeline(trace_path)


def _print_report(report: dict) -> None:
    width = 60
    print("\n" + "=" * width)
    print("  CONTRACT VIOLATION REPORT")
    print("=" * width)
    print(f"  Run ID            : {report['run_id']}")
    print(f"  Workflow          : {report['workflow_name']}")
    print(f"  Violations        : {report['violation_count']}")
    print(f"  Severity          : {report['severity_summary']}")
    print(f"  Failed agent      : {report['failed_agent']} (step {report['failed_step']})")
    print(f"  Root cause        : {report['likely_root_cause']}")
    print(f"  Affected primitive: {report['affected_primitive']}")
    print(f"  Repair patch      : {report['repair_patch']}")
    print(f"  Repair confidence : {report.get('repair_confidence', 0):.2f}")
    print(f"  Regression status : {report['regression_test_status']}")
    print(f"  Approval status   : {report['approval_status']}")
    print(f"\n  Narrative:\n  {report.get('narrative', '').replace(chr(10), chr(10) + '  ')}")
    print("=" * width)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full Zone A + Zone B pipeline.")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Skip Zone A and use existing zone_b/fixtures/sample_trace.json",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  CONCORD LITE — Full Pipeline Run")
    print("=" * 60)

    if args.fixture:
        print("\n[Zone A] Skipped — using fixture trace")
        if not Path(TRACE_PATH).exists():
            print(f"  ERROR: {TRACE_PATH} not found. Run without --fixture first.")
            sys.exit(1)
        print(f"  Trace loaded from {TRACE_PATH}")
    else:
        print("\n[Zone A] Running Literature Review Assistant pipeline...")
        try:
            _run_zone_a()
        except EnvironmentError as e:
            print(f"  ERROR: {e}")
            print("  Tip: run with --fixture to use existing trace without API keys.")
            sys.exit(1)

    print("\n[Zone B] Running diagnostic pipeline...")
    try:
        report = asyncio.run(_run_zone_b(TRACE_PATH))
    except Exception as e:
        print(f"  Zone B pipeline error: {e}")
        sys.exit(1)

    _print_report(report)


if __name__ == "__main__":
    main()
