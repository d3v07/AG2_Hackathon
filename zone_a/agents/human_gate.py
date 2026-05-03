"""Legacy Zone A HumanGate — sequential pipeline only.

In the swarm (zone_a/swarm.py) the HumanGate is a real ConversableAgent gated
by an OnContextCondition. This legacy version stays for the original
zone_a/run.py pipeline and the historical fixture trace generation. It
intentionally returns approval_status="pending" by default to preserve the
broken-by-design behaviour the existing fixture and tests rely on.
"""
from autogen import ConversableAgent, UserProxyAgent

from zone_a.config import get_llm_config


def _ask_human(report: dict) -> tuple[str, str]:
    """Collect a real human decision via AG2 UserProxyAgent (interactive mode)."""
    presenter = ConversableAgent(
        name="HumanGateAgent",
        llm_config=get_llm_config(),
        system_message=(
            "You summarise a research report for a human reviewer in one "
            "concise paragraph and ask them to approve or reject."
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
    chat = reviewer.initiate_chat(
        presenter, message=f"Please review this report: {report}", max_turns=1
    )
    last = chat.chat_history[-1].get("content", "") if chat.chat_history else ""
    text = (last or "").strip().lower()
    if text.startswith("approve") or "approved" in text:
        return "approved", last
    if text.startswith("reject") or "rejected" in text:
        return "rejected", last
    return "pending", last or ""


def run_human_gate(report: dict, interactive: bool = False) -> dict:
    if not interactive:
        agent = ConversableAgent(
            name="HumanGateAgent",
            llm_config=get_llm_config(),
            system_message="You simulate a human reviewer. Acknowledge receipt of the report in one sentence.",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
            code_execution_config=False,
        )
        proxy = UserProxyAgent(
            name="HumanGateProxy",
            llm_config=False,
            human_input_mode="NEVER",
            is_termination_msg=lambda x: True,
            max_consecutive_auto_reply=0,
            code_execution_config=False,
        )
        proxy.initiate_chat(agent, message=f"Please review this report: {report}", max_turns=1)
        return {"approval_status": "pending"}

    status, _ = _ask_human(report)
    return {"approval_status": status}


if __name__ == "__main__":
    report = {"summary": "Test report", "claims": [], "citations": [], "risks": [], "next_steps": []}
    out = run_human_gate(report)
    print(out)
