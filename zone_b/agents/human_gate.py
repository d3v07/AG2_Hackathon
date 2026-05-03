"""HumanGate — final approval check on the Contract Violation Report.

Default is auto-approve for the demo / test runs. With ``interactive=True``
a real ``UserProxyAgent`` collects an approval decision from stdin via the
AG2 framework — the same primitive used by Zone A's swarm.
"""
import asyncio

from autogen import ConversableAgent, UserProxyAgent

from zone_b.config import get_llm_config


def _interactive_decision(report: dict) -> tuple[str, str]:
    """Collect an approve / reject decision via AG2 UserProxyAgent."""
    repair_patch = report.get("repair_patch", "<no patch>")
    affected_primitive = report.get("affected_primitive", "<unknown>")
    confidence = report.get("repair_confidence", 0.0)
    failed_agent = report.get("failed_agent", "<unknown>")

    presenter = ConversableAgent(
        name="HumanGatePresenter",
        llm_config=get_llm_config(),
        system_message=(
            "You present a Contract Violation Report to a human reviewer in one "
            "concise paragraph and ask them to approve or reject the repair."
        ),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )
    reviewer = UserProxyAgent(
        name="HumanReviewer",
        llm_config=False,
        human_input_mode="ALWAYS",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )

    prompt = (
        f"Failed agent       : {failed_agent}\n"
        f"Affected primitive : {affected_primitive}\n"
        f"Confidence         : {confidence:.2f}\n"
        f"Repair patch       : {repair_patch}\n\n"
        "Reply with 'approve' or 'reject' followed by a one-sentence comment."
    )
    chat = reviewer.initiate_chat(presenter, message=prompt, max_turns=1)
    last = chat.chat_history[-1].get("content", "") if chat.chat_history else ""
    text = (last or "").strip().lower()
    if text.startswith("approve") or "approved" in text:
        return "approved", last
    if text.startswith("reject") or "rejected" in text:
        return "rejected", last
    return "pending", last or "no decision recorded"


async def run_human_gate(report: dict, interactive: bool = False) -> dict:
    """Approve / reject the repair proposal.

    interactive=False → auto-approve (default; preserves test behaviour).
    interactive=True  → real UserProxyAgent prompt.
    """
    repair_patch = report.get("repair_patch", "<no patch>")
    affected_primitive = report.get("affected_primitive", "<unknown>")
    confidence = report.get("repair_confidence", 0.0)
    failed_agent = report.get("failed_agent", "<unknown>")

    print("\n=== HumanGate: Repair Proposal ===")
    print(f"Failed agent       : {failed_agent}")
    print(f"Affected primitive : {affected_primitive}")
    print(f"Confidence         : {confidence:.2f}")
    print(f"Repair patch       : {repair_patch}")

    if not interactive:
        print("Decision           : APPROVED (demo auto-approval)")
        return {
            "approval_status": "approved",
            "comments": "Auto-approved for demo run",
        }

    status, comments = _interactive_decision(report)
    print(f"Decision           : {status.upper()}")
    return {"approval_status": status, "comments": comments}


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
