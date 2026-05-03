import json
import time
from autogen import ConversableAgent
from zone_a.config import get_llm_config
from zone_a.agents._utils import make_proxy


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
    proxy = make_proxy("ActionProxy")

    message = f"Execute action based on this report: {json.dumps(final_output)}"
    result = proxy.initiate_chat(agent, message=message, max_turns=1)
    action_taken = result.chat_history[-1]["content"]

    return {
        "step": 5,
        "agent": "ActionAgent",
        "type": "agent_turn",
        "content": action_taken,
        "tool_call_id": None,
        "context_delta": {"action_event": "saved"},
        "handoff_to": None,
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    report = {"summary": "Test", "claims": [], "citations": [], "risks": [], "next_steps": []}
    out = run_action_agent(report, approval_status="pending")
    print(out)
