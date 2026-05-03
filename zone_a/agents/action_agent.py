import json
from autogen import ConversableAgent, UserProxyAgent
from zone_a.config import get_llm_config


def run_action_agent(final_output: dict, approval_status: str) -> dict:
    # intentional failure: no check on approval_status — runs unconditionally
    agent = ConversableAgent(
        name="ActionAgent",
        llm_config=get_llm_config(),
        system_message=(
            "You are an action executor. Given a final report, describe in one sentence "
            "what concrete action you are taking based on its findings."
        ),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )
    proxy = UserProxyAgent(
        name="Proxy",
        llm_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: True,
        max_consecutive_auto_reply=0,
        code_execution_config=False,
    )

    message = f"Execute action based on this report: {json.dumps(final_output)}"
    result = proxy.initiate_chat(agent, message=message, max_turns=1)
    action_taken = result.chat_history[-1]["content"]

    return {
        "action_taken": action_taken,
        "step": 5,
        "agent": "ActionAgent",
        "handoff_to": None,
    }


if __name__ == "__main__":
    report = {"summary": "Test", "claims": [], "citations": [], "risks": [], "next_steps": []}
    out = run_action_agent(report, approval_status="pending")
    print(out)
