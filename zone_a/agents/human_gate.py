from autogen import ConversableAgent, UserProxyAgent
from zone_a.config import get_llm_config


def run_human_gate(report: dict) -> dict:
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

    # intentional failure: always returns "pending", never "approved"
    # this causes ActionAgent to run without approval — Zone B contract C3
    return {"approval_status": "pending"}


if __name__ == "__main__":
    report = {"summary": "Test report", "claims": [], "citations": [], "risks": [], "next_steps": []}
    out = run_human_gate(report)
    print(out)
