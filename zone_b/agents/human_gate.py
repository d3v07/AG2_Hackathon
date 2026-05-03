"""HumanGate — auto-approves the repair proposal for the demo.

Per issue #2: no LLM, just print the repair proposal + confidence and
return approval status. This is the final gate before a Contract
Violation Report is considered ready to act on.
"""
import asyncio


async def run_human_gate(report: dict) -> dict:
    """Approve the repair proposal. Demo always auto-approves."""
    repair_patch = report.get("repair_patch", "<no patch>")
    affected_primitive = report.get("affected_primitive", "<unknown>")
    confidence = report.get("repair_confidence", 0.0)
    failed_agent = report.get("failed_agent", "<unknown>")

    print("\n=== HumanGate: Repair Proposal ===")
    print(f"Failed agent       : {failed_agent}")
    print(f"Affected primitive : {affected_primitive}")
    print(f"Confidence         : {confidence:.2f}")
    print(f"Repair patch       : {repair_patch}")
    print("Decision           : APPROVED (demo auto-approval)")

    return {
        "approval_status": "approved",
        "comments": "Auto-approved for demo run",
    }


if __name__ == "__main__":
    stub_report = {
        "failed_agent": "VerifierAgent",
        "affected_primitive": "Guardrail",
        "repair_patch": "Add OnContextCondition gate before ReporterAgent",
        "repair_confidence": 0.85,
    }
    result = asyncio.run(run_human_gate(stub_report))
    print(f"\n--> approval_status: {result['approval_status']}")
    print(f"--> comments       : {result['comments']}")
